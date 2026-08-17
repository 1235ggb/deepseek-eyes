# deepseek_eyes — MCP 服务器入口
#
# 让 DeepSeek 等无视觉能力的模型，通过本 MCP 服务调用视觉模型识图。
# 默认使用阿里云百炼 (DashScope) 的 OpenAI 兼容接口。
#
# 工具：
#   describe_image              识别一张图片（本地路径 / 网络 URL / data URL）
#   describe_pasted_images      从会话记录提取用户最近粘贴/上传的图片并识别
#   describe_images_in_folder   批量识别一个文件夹里的多张图片
#   get_config                  查看当前识图配置（不显示明文 Key）
#   update_config               修改识图提供商 / 模型 / Base URL
#
# 环境变量：
#   DEEPSEEK_EYES_API_KEY    必填，识图模型的 API Key
#   DEEPSEEK_EYES_BASE_URL   可选，覆盖提供商 Base URL
#   DEEPSEEK_EYES_MODEL      可选，覆盖模型名

import os
import sys
from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

from . import config, session, vision

# 注册到 MCP 服务器名（在客户端里显示为 deepseek_eyes）
server = MCPServer("deepseek_eyes")


@server.tool(description="识别一张图片并返回文字描述。图片可来自本地文件路径、网络 URL(http/https) 或 data URL。")
def describe_image(
    image: Annotated[str, Field(description="图片：本地绝对路径、网络 URL 或 data URL")],
    prompt: Annotated[str, Field(description="识图提问，例如『请描述图中文字』")] = "请详细描述这张图片的内容，尽量全面、具体，用中文回答。",
    url: Annotated[bool, Field(description="True 表示 image 是网络 URL 而非本地路径；通常可省略（会自动识别）")] = False,
) -> str:
    """识别一张图片并返回文字描述。"""
    try:
        if url:
            return vision.describe_image_url(image, prompt)
        return vision.describe_image_file(image, prompt)
    except Exception as e:
        return f"识图失败: {e}"


@server.tool(
    description="扫描一个文件夹中的所有图片，并行识别并返回每张图片的描述。适用于一次识别多张图片（例如把多张截图放进一个文件夹后批量分析）。并行识别，速度较快。"
)
def describe_images_in_folder(
    folder: Annotated[str, Field(description="存放图片的文件夹路径")],
    prompt: Annotated[str, Field(description="对每张图片的识图提问")] = "请详细描述这张图片的内容，尽量全面、具体，用中文回答。",
    recursive: Annotated[bool, Field(description="是否递归扫描子文件夹")] = False,
    limit: Annotated[int, Field(description="最多识别张数（默认 10，防止一次太多）")] = 10,
) -> str:
    """并行识别一个文件夹里的图片。"""
    from pathlib import Path

    p = Path(folder)
    if not p.is_dir():
        return f"文件夹不存在: {p.resolve()}"

    images = []
    for f in sorted(p.rglob("*") if recursive else p.glob("*")):
        if f.is_file() and f.suffix.lower() in vision.IMAGE_MIME:
            images.append(f)

    if not images:
        return f"文件夹中没有找到图片: {p.resolve()}"

    if len(images) > limit:
        images = images[:limit]

    def _recognize(idx: int, img_path: Path) -> str:
        try:
            desc = vision.describe_image_file(str(img_path), prompt)
            return f"[{idx}/{len(images)}] {img_path.name}:\n{desc}"
        except Exception as e:
            return f"[{idx}/{len(images)}] {img_path.name}: 识别失败 - {e}"

    from concurrent.futures import ThreadPoolExecutor

    results = [""] * len(images)
    with ThreadPoolExecutor(max_workers=min(len(images), 5)) as pool:
        futures = {pool.submit(_recognize, i + 1, img): i for i, img in enumerate(images)}
        for fut in futures:
            results[futures[fut]] = fut.result()

    return "\n\n".join(results)


@server.tool(
    description="从会话记录中提取用户最近一次粘贴或上传的图片（单张或多张均可），并行识别并返回每张的描述。适用于对话里图片显示为 [Unsupported Image] 的场景——以用户真正上传到输入框的图片为准，不受剪贴板影响。只处理最近一条含图片的用户消息，避免混入历史图片。"
)
def describe_pasted_images(
    prompt: Annotated[str, Field(description="对每张图片的识图提问")] = "请详细描述这张图片的内容，尽量全面、具体，用中文回答。",
    max_count: Annotated[int, Field(description="最多提取并识别几张最近粘贴/上传的图片（默认 10）")] = 10,
) -> str:
    """从会话记录提取并识别最近粘贴或上传的多张图片（并行）。"""
    try:
        images = session.find_pasted_images(max_count=max_count)
        if not images:
            return "未在会话记录中找到粘贴/上传的图片。请先在输入框粘贴或上传图片，再调用本工具。"

        def _recognize(idx: int, media_type: str, b64_data: str) -> str:
            """识别单张图片，返回结果文本。"""
            path = session.pasted_image_to_temp(media_type, b64_data)
            try:
                desc = vision.describe_image_file(path, prompt)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            return f"[{idx}/{len(images)}] ({media_type.split('/')[-1]}):\n{desc}"

        from concurrent.futures import ThreadPoolExecutor

        results = [""] * len(images)
        with ThreadPoolExecutor(max_workers=min(len(images), 5)) as pool:
            futures = {
                pool.submit(_recognize, i + 1, mt, b64): i
                for i, (mt, b64) in enumerate(images)
            }
            for fut in futures:
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    results[idx] = f"[{idx}/{len(images)}]: 识别失败 - {e}"

        return "\n\n".join(results)
    except Exception as e:
        return f"识别粘贴/上传图片失败: {e}"


@server.tool(description="查看当前识图配置：提供商、模型、Base URL、API Key 是否已设置。不返回明文 Key。")
def get_config() -> str:
    """查看当前识图配置。"""
    try:
        cfg = config.effective_config()
        info = config.redact(cfg)
        preset_name = config.PROVIDERS.get(info["provider"], {}).get("name", "自定义")
        return (
            "当前识图配置:\n"
            f"  提供商: {info['provider']} ({preset_name})\n"
            f"  Base URL: {info['base_url']}\n"
            f"  模型: {info['model']}\n"
            f"  API Key: {info['api_key_masked']} ({info['api_key_source']})"
        )
    except Exception as e:
        return f"读取配置失败: {e}"


@server.tool(description="修改识图配置并持久化到 ~/.deepseek-eyes/config.json。API Key 不写入文件，请通过环境变量 DEEPSEEK_EYES_API_KEY 提供。")
def update_config(
    provider: Annotated[str | None, Field(description="识图提供商：dashscope(阿里百炼,默认) / openai / openrouter / zhipu / moonshot / siliconflow / custom。留空则不改")] = None,
    model: Annotated[str | None, Field(description="视觉模型名，例如 qwen-vl-max。留空则不改")] = None,
    base_url: Annotated[str | None, Field(description="自定义 OpenAI 兼容接口的 Base URL（不含 /chat/completions）。留空则不改")] = None,
) -> str:
    """修改识图配置并持久化。"""
    try:
        updates = {}
        if provider is not None:
            if provider not in config.PROVIDERS:
                return f"未知提供商: {provider}。可选: {', '.join(config.PROVIDERS.keys())}"
            updates["provider"] = provider
        if model is not None and model.strip():
            updates["model"] = model.strip()
        if base_url is not None and base_url.strip():
            updates["base_url"] = base_url.rstrip("/")
        if not updates:
            return get_config()

        cfg = config.save_config_file(updates)
        info = config.redact(cfg)
        return (
            "配置已更新并保存到 ~/.deepseek-eyes/config.json：\n"
            f"  提供商: {info['provider']}\n"
            f"  Base URL: {info['base_url']}\n"
            f"  模型: {info['model']}\n"
            f"  API Key: {info['api_key_masked']} ({info['api_key_source']})\n"
            "提示：API Key 仅从环境变量 DEEPSEEK_EYES_API_KEY 读取，不会写入配置文件。"
        )
    except Exception as e:
        return f"更新配置失败: {e}"


def main():
    # Windows 下确保 stdout 使用 UTF-8，避免中文乱码
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    import asyncio

    asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()
