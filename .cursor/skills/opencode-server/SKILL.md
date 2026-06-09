---
name: opencode-server
description: >-
  Integrates OpenCode Server v1.16.2 on oh-agent VM for LLM calls in the
  签字页管理系统. Covers install, serve, health check, session/message API,
  model selection, structured output response parsing, and known pitfalls
  (free model quota timeout, python -c syntax). Use when configuring LLM
  provider, debugging OpenCode connectivity, or testing AI scenarios end-to-end.
---

# OpenCode Server 集成

## 快速启动与验证

```bash
# 启动
orb -m oh-agent bash -lc 'nohup /home/jimmy/.opencode/bin/opencode serve --port 4096 > /dev/null 2>&1 &'

# 健康检查
orb -m oh-agent curl -s http://localhost:4096/global/health
# → {"healthy":true,"version":"1.16.2"}

# 后端验证
orb -m oh-agent bash -lc 'cd backend && LLM_PROVIDER=opencode uv run uvicorn app.main:app --host 0.0.0.0 --port 8000'
orb -m oh-agent curl -s http://localhost:8000/api/health
# → llm_provider=opencode, llm_available=true
```

## API 要点

| 操作 | 端点 |
|------|------|
| 健康检查 | `GET /global/health` |
| 创建会话 | `POST /session` → `{id: "ses_..."}` |
| 发消息 | `POST /session/{sid}/message` |
| 查 Provider/Model | `GET /provider` |

### 发消息 body

```json
{
  "parts": [{"type": "text", "text": "prompt"}],
  "model": {"providerID": "github-copilot", "modelID": "gpt-5-mini"},
  "format": {"type": "json_schema", "schema": {}}
}
```

### 响应解析优先级

1. `info.structured` — 原生结构化输出（`finish: "tool-calls"`）
2. `parts[].text` — 普通文本
3. `info.content / message / text` — 兜底

## 推荐模型

| 用途 | Provider | Model |
|------|----------|-------|
| 结构化输出（主） | `github-copilot` | `gpt-5-mini` |
| 结构化输出（备） | `opencode` | `mimo-v2.5-free` |

## 已知陷阱

1. **免费模型限额耗尽**：`*-free` 模型挂起不返回 → 换 `gpt-5-mini`
2. **禁止 `python -c` 多行 async**：写成 `.py` 文件再 `orb -m oh-agent uv run python xxx.py`
3. **`info.structured` 为空**：模型不支持 tool calling 或限额耗尽
4. **网络**：OpenCode 监听 `127.0.0.1:4096`，仅 VM 内可访问；后端在 VM 内无需额外配置

## 环境变量（OpenCodeProvider）

| 变量 | 默认 |
|------|------|
| `OPENCODE_BASE_URL` | `http://localhost:4096` |
| `OPENCODE_STRUCTURED_PROVIDER` | `github-copilot` |
| `OPENCODE_STRUCTURED_MODEL` | `gpt-5-mini` |
| `OPENCODE_STRUCTURED_FALLBACK_PROVIDER` | `opencode` |
| `OPENCODE_STRUCTURED_FALLBACK_MODEL` | `mimo-v2.5-free` |

## 详细参考

API 实测细节与端到端验证脚本见 [reference.md](reference.md)。
