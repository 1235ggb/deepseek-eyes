# 剪贴板图片读取 & 会话粘贴图片提取
#
# 背景：很多接入 DeepSeek 的客户端不支持把粘贴的图片作为附件传给模型，
# 模型收到的只是一个 "[Unsupported Image]" 占位符，拿不到图片。
# 但有两种方式可以拿到图片真实数据：
#   1. 系统剪贴板（只保留最后复制的一张）
#   2. Claude Code 的会话记录文件（~/.claude/projects/**/*.jsonl）——
#      粘贴/上传的图片会以 base64 完整保存，包括同一批的多张图
#
# 实现：
#   Windows 剪贴板：用 Pillow 的 ImageGrab.grabclipboard()，成熟稳定。
#   会话记录：扫描最新会话文件，提取用户消息里的 image 内容块。

import base64
import hashlib
import json
import os
import tempfile
from pathlib import Path

from PIL import Image, ImageGrab


def read_clipboard_image() -> tuple[str, bytes] | None:
    """读取剪贴板中的图片，返回 (扩展名, 图片字节)；剪贴板没有图片返回 None。

    返回的是 PNG 编码的字节（保存前统一转 PNG，透明通道也能保留）。
    """
    img = ImageGrab.grabclipboard()
    if img is None:
        return None
    if not isinstance(img, Image.Image):
        # 剪贴板里是文件列表 / 文本等非图片内容
        return None

    # 统一转成 PNG 字节
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, format="PNG")
    return "png", buf.getvalue()


def save_clipboard_image_to_temp() -> str | None:
    """把剪贴板图片保存到临时目录，返回文件路径；剪贴板没有图片返回 None。"""
    img = read_clipboard_image()
    if not img:
        return None
    ext, data = img
    fd, path = tempfile.mkstemp(
        suffix=f".{ext}", prefix="deepseek_eyes_", dir=os.environ.get("TEMP")
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        return path
    except OSError:
        try:
            os.remove(path)
        except OSError:
            pass
        raise


def _session_files() -> list[Path]:
    """返回会话记录文件，按最后修改时间倒序。

    支持客户端：
      Claude Code: ~/.claude/projects/**/*.jsonl
      Codex CLI:   ~/.codex/sessions/**/rollout-*.jsonl
      Cursor: 图片存成文件在 workspaceStorage/*/images/*.png（由 _cursor_images 收集）
    """
    bases = [
        Path.home() / ".claude" / "projects",  # Claude Code
        Path.home() / ".codex" / "sessions",   # Codex CLI
    ]

    appdata = os.environ.get("APPDATA", "")

    files: list[Path] = []
    for base in bases:
        if not base.is_dir():
            continue
        try:
            files.extend(p for p in base.rglob("*.jsonl") if p.is_file())
        except OSError:
            continue

    # Cursor：粘贴/上传的图片直接以文件存在 workspaceStorage/*/images/
    if appdata:
        cursor_base = Path(appdata) / "Cursor" / "User" / "workspaceStorage"
        if cursor_base.is_dir():
            try:
                files.extend(_cursor_images(cursor_base))
            except OSError:
                pass

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _cursor_images(base: Path) -> list[Path]:
    """收集 Cursor 存下来的粘贴图片文件。"""
    imgs = []
    for d in base.rglob("images"):
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
                imgs.append(f)
    return imgs


def _extract_image_data(d: dict) -> list[tuple[str, str]]:
    """从一条会话记录里提取图片，返回 [(media_type, base64_data), ...]。

    兼容客户端格式：
      Claude Code: type=="user", message.content[].image.source={type, media_type, data}
      Codex CLI:   payload.content[].image_url.url="data:image/...;base64,..."
    """
    found: list[tuple[str, str]] = []
    if not isinstance(d, dict):
        return found

    # --- 定位 content 列表（Claude Code 在 message.content；也兼容顶层 content）---
    content = None
    if d.get("type") == "user":
        msg = d.get("message", {})
        if isinstance(msg, dict):
            content = msg.get("content")
    if content is None:
        content = d.get("content")

    # --- 通用：content[].image.source.data ---
    if isinstance(content, list):
        for c in content:
            if not (isinstance(c, dict) and c.get("type") == "image"):
                continue
            src = c.get("source", {})
            data = src.get("data", "")
            if data:
                found.append((src.get("media_type", "image/png"), data))

    # --- Codex 格式：payload.content[].image_url.url = data:...;base64,... ---
    payload = d.get("payload", d)
    if isinstance(payload, dict):
        content = payload.get("content", [])
        if isinstance(content, list):
            for c in content:
                if not (isinstance(c, dict) and c.get("type") == "image_url"):
                    continue
                url = (c.get("image_url") or {}).get("url", "")
                if url.startswith("data:"):
                    # data:image/png;base64,XXX
                    header, _, b64 = url.partition(",")
                    media_type = header[len("data:"):].split(";")[0] or "image/png"
                    if b64:
                        found.append((media_type, b64))

    return found


def _iter_json_objects(p: Path):
    """逐条产出文件里的 JSON 对象。

    Claude/Codex 是 jsonl（每行一个对象）；也兼容整个文件是一个 JSON 数组的情况。
    统一处理成迭代器。
    """
    try:
        with open(p, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return
    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            arr = json.loads(stripped)
            if isinstance(arr, list):
                for item in reversed(arr):
                    yield item
                return
        except json.JSONDecodeError:
            pass  # 不是完整数组，退回按行解析
    # jsonl：逐行解析
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def find_pasted_images(max_count: int = 20) -> list[tuple[str, str]]:
    """从最近的会话记录（Claude Code + Codex + Cursor）中提取用户粘贴/上传的图片。

    返回 [(media_type, base64_data), ...]，按消息时间从新到旧。
    同一张图按内容去重（避免跨会话重复）。
    """
    images: list[tuple[str, str]] = []
    seen: set[str] = set()

    # 扫描所有会话文件（不限制前 N 个，避免漏掉早期但含图的文件），
    # 从最新到最旧，提取到 max_count 张就停。
    for p in _session_files():
        # --- Cursor 图片文件：直接读文件转 base64 ---
        # （Cursor 的图片不在 json 里，而以文件存在 images/ 目录）
        cursor_png = "workspaceStorage" in str(p)
        if cursor_png:
            try:
                with open(p, "rb") as f:
                    raw = f.read()
                if not raw:
                    continue
                b64 = base64.b64encode(raw).decode("ascii")
                ext = p.suffix.lower().lstrip(".")
                media_type = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "gif": "image/gif"}.get(ext, "image/png")
                h = hashlib.md5(raw).hexdigest()
                if h not in seen:
                    seen.add(h)
                    images.append((media_type, b64))
                if len(images) >= max_count:
                    return images
                continue
            except OSError:
                continue

        # --- json 会话文件：逐对象提取 ---
        for d in _iter_json_objects(p):
            for media_type, data in _extract_image_data(d):
                if not data:
                    continue
                h = hashlib.md5(data.encode("utf-8")).hexdigest()
                if h not in seen:
                    seen.add(h)
                    images.append((media_type, data))
                if len(images) >= max_count:
                    return images
    return images


def pasted_image_to_temp(media_type: str, b64_data: str) -> str:
    """把会话里的 base64 图片写到临时文件，返回路径。"""
    raw = base64.b64decode(b64_data)
    ext = "png" if "png" in media_type else ("jpg" if "jpeg" in media_type else "img")
    fd, path = tempfile.mkstemp(
        suffix=f".{ext}", prefix="deepseek_eyes_", dir=os.environ.get("TEMP")
    )
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        return path
    except OSError:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
