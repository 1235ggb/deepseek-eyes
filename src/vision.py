# 视觉模型调用：图片 → base64 → OpenAI 兼容格式 → 文字描述
#
# 与参考项目 vision.js 思路一致，但改造成可在 MCP 内复用的纯函数：
#   - describe_image_file(path, prompt)
#   - describe_image_url(url, prompt)

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path

from . import config

# 常见图片扩展名 → MIME 类型
IMAGE_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _guess_mime(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in IMAGE_MIME:
        return IMAGE_MIME[ext]
    guessed, _ = mimetypes.guess_type(path)
    return guessed or "image/jpeg"


def file_to_data_url(path: str) -> str:
    """本地图片文件 → data URL（data:image/...;base64,...）。

    过大的图片先压缩尺寸，减少视觉模型处理负载、加快识别速度。
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"文件不存在: {p.resolve()}")
    data = p.read_bytes()

    # 压缩：超过 MAX_DIM / MAX_BYTES 的图先缩放再重编码，返回 (新字节, 新格式)
    try:
        data, fmt = _maybe_downscale(data)
    except Exception:
        fmt = _guess_mime(str(p))  # 压缩失败就发原图
    if not fmt:
        fmt = _guess_mime(str(p))
    return f"data:{fmt};base64,{base64.b64encode(data).decode('ascii')}"


# 视觉模型常见限制：单边最长像素 & 文件大小
# 1280 是实测性价比最优：大图缩到 1280px 后识别明显更快，且质量不损失
MAX_DIM = 1280
MAX_BYTES = 4 * 1024 * 1024


def _maybe_downscale(data: bytes) -> tuple[bytes, str]:
    """如果图片太大，缩放到 MAX_DIM 以内并重新编码。

    返回 (新图片字节, 新的 MIME 类型)。尺寸和大小都合理时原样返回。
    """
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(data))
    img.load()

    w, h = img.size
    if w <= MAX_DIM and h <= MAX_DIM and len(data) <= MAX_BYTES:
        return data, img.get_format_mimetype() or "image/png"

    # 等比缩放
    scale = min(1.0, MAX_DIM / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)

    # 重新编码：带透明通道用 PNG，否则用 JPEG 压缩更小
    out = BytesIO()
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img.save(out, format="PNG")
        return out.getvalue(), "image/png"
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, format="JPEG", quality=85)
        return out.getvalue(), "image/jpeg"


def _is_data_url(s: str) -> bool:
    return s.startswith("data:") and ";base64," in s


def build_payload(image_ref: str, prompt: str, is_url: bool) -> dict:
    """构造 OpenAI 兼容的多模态消息体。image_ref 是本地路径或 URL。"""
    if is_url or image_ref.startswith(("http://", "https://")):
        url = image_ref
    elif _is_data_url(image_ref):
        url = image_ref
    else:
        url = file_to_data_url(image_ref)

    payload = {
        "model": _model(),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "stream": False,
        "max_tokens": 1024,
    }

    # 默认关闭思考模式（reasoning）：qwen3 系列开启思考会明显变慢（实测 12s→4s）。
    # 若某些模型不接受该参数，用 DEEPSEEK_EYES_THINKING=1 或改配置文件重新开启。
    if os.environ.get("DEEPSEEK_EYES_THINKING", "0") != "1":
        payload["enable_thinking"] = False

    return payload


def _model() -> str:
    return config.effective_config()["model"]


def _chat_url() -> str:
    cfg = config.effective_config()
    base = cfg["base_url"].rstrip("/")
    return base + "/chat/completions"


def _headers(payload_len: int) -> dict:
    cfg = config.effective_config()
    api_key = cfg.get("api_key") or ""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Content-Length": str(payload_len),
    }


def call_vision(payload: dict) -> str:
    """发送请求并返回模型输出文本。"""
    cfg = config.effective_config()
    if not cfg.get("api_key"):
        raise RuntimeError(
            "未配置 DEEPSEEK_EYES_API_KEY 环境变量。\n"
            "请在设置 MCP 服务器时添加环境变量，或在阿里云百炼控制台获取："
            "https://bailian.console.aliyun.com/"
        )

    url = _chat_url()
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers=_headers(len(body)),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"API {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络错误: {e.reason}") from e

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"API 返回非 JSON: {raw[:300]}") from e

    if data.get("error"):
        raise RuntimeError(f"API 错误: {json.dumps(data['error'], ensure_ascii=False)}")

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"响应解析失败: {raw[:300]}") from e


def describe_image_file(path: str, prompt: str = "请详细描述这张图片的内容。") -> str:
    payload = build_payload(path, prompt, is_url=False)
    return call_vision(payload)


def describe_image_url(url: str, prompt: str = "请详细描述这张图片的内容。") -> str:
    payload = build_payload(url, prompt, is_url=True)
    return call_vision(payload)
