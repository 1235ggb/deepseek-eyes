# 👁️ DeepSeek Eyes

> **给 DeepSeek 装上一双眼睛。**
> 让没有视觉能力的 DeepSeek 也能「看图」——把图片交给视觉模型，用文字描述回传。

一个通用的 **MCP 服务器**，让 **DeepSeek 等无视觉模型获得图像识别能力**。适配 **Claude Code、Codex、Cursor** 等主流 AI 编程工具，无需改任何项目代码。

---

## 为什么需要它

DeepSeek 是顶尖的**文本模型**，但没有视觉能力。你给它一张图，它只会看到一团乱码：

```
用户: [粘贴了一张截图]
DeepSeek: 我无法查看图片……（无能为力）
```

**DeepSeek Eyes** 给 DeepSeek 装上「义眼」：

```
用户: [粘贴了一张截图] 图里写了什么？
DeepSeek Eyes MCP → 读图 → 文字描述（"页面显示 DNS 解析失败…"）
DeepSeek: 这张图显示的是 DNS_PROBE_FINISHED_NXDOMAIN 错误页……
```

**它自己看图，把看到的用文字讲给 DeepSeek。** 就像给看不见的模型配了一位解说员。

---

## ✨ 特性

- 🖼️ **五个 MCP 工具**：识图、会话图片找回、批量识图、配置查看/修改
- 💾 **会话图片找回**：粘贴图片但客户端传不了图（显示 `[Unsupported Image]`）？从 Claude Code / Codex / Cursor 的会话记录里提取你**最近一次**粘贴/上传的图片——以真正上传到输入框的图片为准，单张、多张都能识别，不受剪贴板影响
- 🗂️ **批量识图**：一键识别文件夹里的所有图片
- 🔌 **多提供商**：阿里百炼 / OpenAI / OpenRouter / 智谱 / Moonshot / 硅基流动 / 自定义
- 🚀 **快速**：并行识别 + 图片压缩 + 关闭思考模式 → 3 张图约 5 秒
- 🔑 **Key 安全**：API Key 只走环境变量，永不写入配置文件

---

## 🧠 适配主流 AI 工具

| 工具 | 会话图片找回 | 配置方式 |
|------|:---:|------|
| **Claude Code** | ✅ `~/.claude/projects/*.jsonl` | `~/.claude.json` |
| **Codex CLI** | ✅ `~/.codex/sessions/*/rollout-*.jsonl` | `~/.codex/config.toml` |
| **Cursor** | ✅ `workspaceStorage/*/images/*.png` | `~/.cursor/.mcp.json` |

> 其他支持 MCP 的客户端理论上也能接，配置结构相同（`command` / `args` / `env`）。

---

## 🚀 安装

需要 **Python 3.10+**。

```bash
# 1. 克隆
git clone https://github.com/<你的用户名>/deepseek-eyes.git
cd deepseek-eyes

# 2. 建虚拟环境并安装
python -m venv .venv
# Windows:
.venv\Scripts\pip install -e .
# macOS / Linux:
.venv/bin/pip install -e .
```

---

## 🔑 配置：获取 API Key

默认使用**阿里云百炼**（新用户有免费额度，国内直连）：

1. 打开 [阿里云百炼控制台](https://bailian.console.aliyun.com/) 并登录
2. 右上角 → **API-KEY** → 创建新的 API Key
3. 复制 `sk-` 开头的 Key

之后把 Key 设成环境变量（**不要写进仓库**）：

```bash
# Windows (PowerShell)
$env:DEEPSEEK_EYES_API_KEY = "sk-你的Key"
# macOS / Linux
export DEEPSEEK_EYES_API_KEY="sk-你的Key"
```

---

## ⚙️ 接入 MCP 客户端

### Claude Code

编辑 `~/.claude.json`，在 `mcpServers` 中加入：

```json
{
  "mcpServers": {
    "deepseek_eyes": {
      "command": "C:\\path\\to\\deepseek-eyes\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src"],
      "cwd": "C:\\path\\to\\deepseek-eyes",
      "env": {
        "DEEPSEEK_EYES_API_KEY": "sk-你的Key",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

### Codex CLI

编辑 `~/.codex/config.toml`：

```toml
[mcp_servers.deepseek_eyes]
enabled = true
command = "C:\\path\\to\\deepseek-eyes\\.venv\\Scripts\\python.exe"
args = ["-m", "src"]
cwd = "C:\\path\\to\\deepseek-eyes"

[mcp_servers.deepseek_eyes.env]
DEEPSEEK_EYES_API_KEY = "sk-你的Key"
PYTHONIOENCODING = "utf-8"
```

### Cursor

创建 `~/.cursor/.mcp.json`：

```json
{
  "mcpServers": {
    "deepseek_eyes": {
      "command": "C:\\path\\to\\deepseek-eyes\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src"],
      "cwd": "C:\\path\\to\\deepseek-eyes",
      "env": {
        "DEEPSEEK_EYES_API_KEY": "sk-你的Key",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

> 💡 Windows 下建议加 `PYTHONIOENCODING: "utf-8"` 避免中文乱码。
> 完整配置模板见 [MCP_CONFIG_EXAMPLE.md](MCP_CONFIG_EXAMPLE.md)。

**重启客户端**后即可生效。

---

## 📖 使用

接入后，对 DeepSeek 说：

```
识别这张图片 C:\path\to\image.png
```

它会自动调用视觉模型识图，把结果用文字告诉你。

### 常用场景

| 场景 | 做法 |
|------|------|
| 粘贴图片 | 直接粘贴，问「图里是什么」 |
| 粘贴多张图片 | 一次全贴，说「识别我粘贴的这几张图片」 |
| 图片在本地 | `describe_image(image="C:\\path\\img.png")` |
| 图片在文件夹 | `describe_images_in_folder(folder="C:\\path\\folder")` |
| 网络图片 | `describe_image(image="https://...")` |

### 五个工具

| 工具 | 作用 |
|------|------|
| `describe_image` | 识别单张图片（本地路径 / URL / data URL） |
| `describe_pasted_images` | **从会话记录提取最近一次粘贴/上传的图片**并识别（粘贴识图首选，单张/多张均可） |
| `describe_images_in_folder` | 批量识别文件夹里的所有图片 |
| `get_config` | 查看当前识图配置（不显示明文 Key） |
| `update_config` | 切换提供商 / 模型 / Base URL |

---

## 🧠 思考能力（Thinking）的影响

识图模型（如 qwen3 系列）默认开启**思考模式（reasoning）**：识图前先「想半天」，让识别变慢数倍。

**DeepSeek Eyes 默认关闭思考模式**（`enable_thinking: false`），实测：

| 模式 | 单张识别耗时 |
|------|------------|
| 思考模式开启 | **12.3 秒** |
| 思考模式关闭 | **4.4 秒** ⚡ |

关闭后**快约 3 倍**，且不影响识别质量。如果你希望保留模型的深度思考（某些复杂场景）：

```bash
# 环境变量开启思考模式
DEEPSEEK_EYES_THINKING=1
```

> 注意：不同视觉模型对 `enable_thinking` 参数的支持不同。若不支持该参数的模型，可保持默认关闭。

### 其他速度优化

- 🖼️ **图片压缩**：超过 1280px 的图自动等比压缩，减少视觉模型处理负载
- ⚡ **并行识别**：多张图片同时识别，总耗时 ≈ 最慢一张

---

## 🗂️ 支持的提供商与默认模型

| 提供商 | `provider` 值 | 默认模型 | 备注 |
|--------|--------------|----------|------|
| 阿里云百炼 | `dashscope` | `qwen3.7-flash-2026-07-15` | 新用户免费额度，国内直连 |
| OpenAI | `openai` | `gpt-4o-mini` | 需海外支付 |
| OpenRouter | `openrouter` | `qwen/qwen2.5-vl-72b-instruct` | 聚合多家模型 |
| 智谱 | `zhipu` | `glm-4v-flash` | 有免费额度 |
| Moonshot | `moonshot` | `moonshot-v1-8k-vision-preview` | 国内直连 |
| 硅基流动 | `siliconflow` | `Qwen/Qwen2.5-VL-72B-Instruct` | 开源视觉模型多 |
| 自定义 | `custom` | — | 自填 `base_url` |

切换提供商/模型，只需对 DeepSeek 说「把识图模型换成 `xxx`」即可。

---

## 🧩 工作原理

```
[用户] 粘贴/上传图片
   │
   ▼
[DeepSeek Eyes MCP]  ← 从会话记录 / 路径获取图片
   │
   ▼  base64 → OpenAI 兼容格式
[视觉模型 (qwen3.7-flash)]  ← 阿里百炼等
   │
   ▼  文字描述
[DeepSeek]  ← 用文字描述回答用户
```

图片永远不会直接喂给 DeepSeek（它看不懂），而是由 DeepSeek Eyes 变成文字后"转述"给 DeepSeek。

---

## 🛡️ 安全

- **API Key 只走环境变量**，绝不写入配置文件、不提交到仓库
- `get_config` 只显示脱敏 Key（`sk-w****U-Oi`）
- `.gitignore` 已忽略 `.claude/`、`config.json` 等本地敏感文件

---

## ⚖️ License

MIT
