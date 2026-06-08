# OpenCode Server 集成

> OpenCode Server v1.16.2 在 oh-agent VM 内的安装、配置与 API 要点。

## 安装

已安装在 oh-agent VM：
- 路径：`/home/jimmy/.opencode/bin/opencode`
- 版本：1.16.2

如需重装：
```bash
orb -m oh-agent curl -fsSL https://opencode.ai/install | bash
```

## 启动

```bash
orb -m oh-agent nohup /home/jimmy/.opencode/bin/opencode serve --port 4096 > /dev/null 2>&1 &
```

默认监听 `127.0.0.1:4096`。

## 验证

```bash
orb -m oh-agent curl -s http://localhost:4096/global/health
# → {"healthy":true,"version":"1.16.2"}
```

## OpenCode API 要点

后端 `OpenCodeProvider` 的连接细节（v1.16.2 实测）：

| 行为 | 请求 | 说明 |
|------|------|------|
| 健康检查 | `GET /global/health` | 返回 `{healthy: bool, version: str}` |
| 创建会话 | `POST /session` | body 可为空，返回 `{id: "ses_..."}` |
| 发消息 | `POST /session/{sid}/message` | body: `{parts: [{type: "text", text: "prompt"}]}` |
| 取回复 | 从响应 `parts[]` 中找到 `type="text"` 的 `text` 字段 | 响应含 `{info: {...}, parts: [...]}` |

## 启用 OpenCode LLM 模式

```bash
# 1. 确保 OpenCode Server 在运行
orb -m oh-agent curl -s http://localhost:4096/global/health

# 2. 启动后端
orb -m oh-agent LLM_PROVIDER=opencode uv run uvicorn app.main:app --port 8000

# 3. 验证
orb -m oh-agent curl -s http://localhost:8000/api/health
# → {"llm_provider":"opencode","llm_available":true}
```

## 端到端验证

```bash
orb -m oh-agent uv run python -c "
import asyncio, os
os.environ['LLM_PROVIDER'] = 'opencode'
from app.services.llm.factory import reset_llm_provider; reset_llm_provider()
from app.services.ai_service import parse_template_variables

async def test():
    r = await parse_template_variables('公司：{{name}}, 日期：{{date}}')
    print('OK:', r)

asyncio.run(test())
"
```
