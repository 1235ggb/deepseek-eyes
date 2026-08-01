# 配置加载与持久化
#
# 配置优先级（高 → 低）：
#   1. 环境变量：DEEPSEEK_EYES_API_KEY / DEEPSEEK_EYES_BASE_URL / DEEPSEEK_EYES_MODEL
#   2. 配置文件：~/.deepseek-eyes/config.json（由 get_config / update_config 读写）
#   3. 内置默认值（阿里云百炼 + 默认模型）
#
# 建议把 API Key 放在环境变量里（git 不会泄露），配置文件只存 base_url / model。

import os
import json
from pathlib import Path

# 内置提供商预设（均为 OpenAI 兼容格式）
PROVIDERS = {
    "dashscope": {
        "name": "阿里云百炼 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen3.7-flash-2026-07-15",
        "note": "新用户有免费额度；模型如 qwen3.7-flash / qwen-vl-max / qwen3.5-omni-plus",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "note": "需要海外支付方式",
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "qwen/qwen2.5-vl-72b-instruct",
        "note": "聚合多家模型，需在平台充值",
    },
    "zhipu": {
        "name": "智谱 (Zhipu GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4v-flash",
        "note": "glm-4v-flash 有免费额度",
    },
    "moonshot": {
        "name": "Moonshot Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k-vision-preview",
        "note": "国内直连",
    },
    "siliconflow": {
        "name": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-VL-72B-Instruct",
        "note": "提供多款开源视觉模型",
    },
    "custom": {
        "name": "自定义 (OpenAI 兼容)",
        "base_url": "",
        "default_model": "",
        "note": "任意 OpenAI 兼容接口，自填 base_url",
    },
}

CONFIG_PATH = Path.home() / ".deepseek-eyes" / "config.json"

# 文件配置默认值（不含敏感信息；API Key 走环境变量）
DEFAULTS = {
    "provider": "dashscope",
    "base_url": PROVIDERS["dashscope"]["base_url"],
    "model": PROVIDERS["dashscope"]["default_model"],
}

# 说明：最终生效的 API Key 总是从环境变量 DEEPSEEK_EYES_API_KEY 读取，
# 因此 get_config 返回的配置对象里不会包含明文 Key。


def _ensure_config_dir():
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_config_file() -> dict:
    """读取配置文件；不存在或损坏时返回内置默认值。"""
    try:
        if CONFIG_PATH.exists():
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                merged = dict(DEFAULTS)
                merged.update(raw)
                return merged
    except (json.JSONDecodeError, OSError):
        pass
    return dict(DEFAULTS)


def effective_config() -> dict:
    """合并环境变量、配置文件、内置默认值，得到最终生效的配置。"""
    cfg = load_config_file()

    # 环境变量覆盖配置文件
    if os.environ.get("DEEPSEEK_EYES_API_KEY"):
        cfg["api_key"] = os.environ["DEEPSEEK_EYES_API_KEY"]
    if os.environ.get("DEEPSEEK_EYES_BASE_URL"):
        cfg["base_url"] = os.environ["DEEPSEEK_EYES_BASE_URL"]
    if os.environ.get("DEEPSEEK_EYES_MODEL"):
        cfg["model"] = os.environ["DEEPSEEK_EYES_MODEL"]

    # 提供商预设缺省补全
    provider = cfg.get("provider", "dashscope")
    preset = PROVIDERS.get(provider, PROVIDERS["custom"])
    if not cfg.get("base_url"):
        cfg["base_url"] = preset["base_url"]
    if not cfg.get("model"):
        cfg["model"] = preset["default_model"]

    return cfg


def save_config_file(updates: dict) -> dict:
    """把 update_config 的字段合并写入配置文件，返回持久化后的完整配置（含脱敏）。"""
    _ensure_config_dir()
    cfg = load_config_file()

    # 只接受已知键；空字符串视为清除（回退到默认）
    allowed = {"provider", "base_url", "model"}
    for key in allowed:
        if key in updates:
            value = (updates.get(key) or "").strip()
            if value:
                cfg[key] = value
            else:
                cfg.pop(key, None)

    # 切换提供商时，若用户没有显式传 base_url / model，套用该提供商的预设
    if "provider" in updates and updates.get("provider"):
        preset = PROVIDERS.get(updates["provider"], PROVIDERS["custom"])
        if "base_url" not in updates and preset.get("base_url"):
            cfg["base_url"] = preset["base_url"]
        if "model" not in updates and preset.get("default_model"):
            cfg["model"] = preset["default_model"]

    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return effective_config()


def redact(cfg: dict) -> dict:
    """返回用于展示的配置：隐藏 Key，标记哪些字段来自环境变量。"""
    out = {
        "provider": cfg.get("provider", "dashscope"),
        "base_url": cfg.get("base_url", ""),
        "model": cfg.get("model", ""),
        "api_key_set": bool(cfg.get("api_key")),
    }
    if cfg.get("api_key"):
        k = cfg["api_key"]
        out["api_key_masked"] = k[:4] + "****" + k[-4:]
        out["api_key_source"] = "env:DEEPSEEK_EYES_API_KEY" if os.environ.get("DEEPSEEK_EYES_API_KEY") else "file"
    else:
        out["api_key_masked"] = "(未设置)"
        out["api_key_source"] = "none"
    return out
