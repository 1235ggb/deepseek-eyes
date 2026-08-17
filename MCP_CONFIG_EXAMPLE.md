# deepseek_eyes MCP 接入配置示例

> ⚠️ 以下配置里的 `YOUR_API_KEY` 是占位符，请替换为你自己的阿里云百炼 API Key。
> 千万不要把你的真实 Key 写进仓库或提交到 GitHub。

## 获取 API Key

1. 打开 [阿里云百炼控制台](https://bailian.console.aliyun.com/)
2. 右上角 → API-KEY → 创建新的 API Key（新用户有免费额度）
3. 复制 `sk-` 开头的 Key

## 接入方式（按客户端）

### Claude Code

在 `~/.claude.json`（全局）或项目 `.mcp.json` 中：

```json
{
  "mcpServers": {
    "deepseek_eyes": {
      "command": "C:\\Users\\你的用户名\\deepseek-eyes\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src"],
      "cwd": "C:\\Users\\你的用户名\\deepseek-eyes",
      "env": {
        "DEEPSEEK_EYES_API_KEY": "sk-YOUR_API_KEY",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

### Codex CLI

在 `~/.codex/config.toml` 中：

```toml
[mcp_servers.deepseek_eyes]
enabled = true
command = "C:\\Users\\你的用户名\\deepseek-eyes\\.venv\\Scripts\\python.exe"
args = ["-m", "src"]
cwd = "C:\\Users\\你的用户名\\deepseek-eyes"

[mcp_servers.deepseek_eyes.env]
DEEPSEEK_EYES_API_KEY = "sk-YOUR_API_KEY"
PYTHONIOENCODING = "utf-8"
```

### Cursor

在 `~/.cursor/.mcp.json` 中：

```json
{
  "mcpServers": {
    "deepseek_eyes": {
      "command": "C:\\Users\\你的用户名\\deepseek-eyes\\.venv\\Scripts\\python.exe",
      "args": ["-m", "src"],
      "cwd": "C:\\Users\\你的用户名\\deepseek-eyes",
      "env": {
        "DEEPSEEK_EYES_API_KEY": "sk-YOUR_API_KEY",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

## 工具说明

| 工具 | 说明 |
|------|------|
| `describe_image` | 识别单张图片（本地路径 / URL / data URL）|
| `describe_pasted_images` | 从会话记录提取并识别最近一次粘贴/上传的图片（单张/多张均可） |
| `describe_images_in_folder` | 批量识别文件夹里的图片 |
| `get_config` / `update_config` | 查看 / 修改识图配置 |

## 安全提醒

- API Key 只通过环境变量 `DEEPSEEK_EYES_API_KEY` 注入，代码里不写死
- 不要把 `~/.deepseek-eyes/config.json`、`.claude/`、任何含 Key 的本地配置提交到 git
