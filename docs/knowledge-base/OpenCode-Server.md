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

---

## OpenCode Server API 要点

后端 `OpenCodeProvider` 的连接细节（v1.16.2 实测）：

| 行为 | 请求 | 说明 |
|------|------|------|
| 健康检查 | `GET /global/health` | 返回 `{healthy: bool, version: str}` |
| 创建会话 | `POST /session` | body 可为空，返回 `{id: "ses_..."}` |
| 发消息 | `POST /session/{sid}/message` | body: `{parts, system?, model?, format?}` |
| 取回复 | `response.info.structured` 或 `response.parts[].text` | 见下方「响应解析」 |
| 查询所有 Provider/Model | `GET /provider` | 返回 `{all: [...], connected: [...], default: {...}}` |

### 发消息 body 完整结构

```json
{
  "parts": [{"type": "text", "text": "prompt内容"}],
  "system": "系统提示（可选）",
  "model": {"providerID": "github-copilot", "modelID": "gpt-5-mini"},
  "format": {"type": "json_schema", "schema": { ...JSON Schema... }}
}
```

### 响应解析优先级

1. `info.structured` — 原生结构化输出时有值（`finish: "tool-calls"`）
2. `parts[].text` — 普通文本回复时从 parts 中找 `type="text"` 的项
3. `info.content / message / text` — 兜底字段

---

## Provider 与 Model 管理

### 查询已连接的 Provider

```bash
orb -m oh-agent curl -s http://localhost:4096/provider | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('connected:', d['connected'])
"
# → connected: ['github-copilot', 'opencode']
```

### 查询某 Provider 下所有 Model

```bash
orb -m oh-agent python3 -c "
import json, urllib.request
data = json.load(urllib.request.urlopen('http://localhost:4096/provider'))
p = next(x for x in data['all'] if x['id'] == 'github-copilot')
print(list(p['models'].keys()))
"
```

### GitHub Copilot 当前可用模型（v1.16.2 实测）

```
gpt-5-mini       ← 推荐，支持结构化输出，速度快，免费订阅可用
gpt-5.4
gpt-5.5
gpt-5.3-codex
gpt-5.4-mini
gemini-3-flash-preview
gemini-2.5-pro
gemini-3.1-pro-preview
gemini-3.5-flash
claude-sonnet-4.6   ← OpenCode Server 默认模型
...（共 16 个）
```

> 注意：模型列表随 OpenCode 版本更新变化，以实际 `/provider` 响应为准。

---

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

---

## 端到端验证

> **注意**：不要用 `python -c "..."` 内联多行 async 代码，Python 解析器会报语法错误。
> 应写成临时 .py 文件再执行。

```bash
# 写文件
cat > /Users/jimmy/Workspaces/junhe-mvp/backend/test_llm_tmp.py << 'EOF'
import asyncio, os
os.environ['LLM_PROVIDER'] = 'opencode'
from app.services.llm.factory import reset_llm_provider
reset_llm_provider()
from app.services.ai_service import parse_template_variables

async def main():
    r = await parse_template_variables('公司：{{target_company_name}} 日期：{{signing_date}}')
    print('OK:', r)

asyncio.run(main())
EOF

# 在 VM 内执行（注意 workdir 必须是 backend/）
orb -m oh-agent uv run python test_llm_tmp.py

# 清理
rm /Users/jimmy/Workspaces/junhe-mvp/backend/test_llm_tmp.py
```

---

## 已知问题与陷阱

### 1. 免费模型限额耗尽 → 调用无限超时

**现象**：调用 `mimo-v2.5-free` 等 `*-free` 模型时，请求挂起不返回（不报错，直接超时）。

**识别方法**：
```bash
# 直接 curl 测试，看是否在 60s 内返回
SID=$(orb -m oh-agent curl -s -X POST http://localhost:4096/session | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
orb -m oh-agent curl -s -m 30 -X POST "http://localhost:4096/session/$SID/message" \
  -H 'Content-Type: application/json' \
  -d '{"parts":[{"type":"text","text":"hi"}],"model":{"providerID":"opencode","modelID":"mimo-v2.5-free"}}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('info',{}).get('finish'))"
```
如果 30 秒无响应或报 `curl: (28) Operation timed out`，则该模型限额已耗尽。

**解决**：切换到有 Copilot 订阅的模型，如 `github-copilot/gpt-5-mini`。

---

### 2. Python `-c` 内联多行代码语法报错

**现象**：
```bash
orb -m oh-agent uv run python -c "
async def main():
    ...
asyncio.run(main())
"
# → SyntaxError: invalid syntax
```

**原因**：shell 对 `\n` 的处理在 `-c` 模式下不可靠，异步函数定义尤其容易出错。

**解决**：写成 `.py` 文件再执行（见「端到端验证」）。

---

### 3. 结构化输出时 `info.structured` 为空

**现象**：调用带 `format` 的请求，但响应 `info.structured` 为 `null`。

**可能原因**：
- 该模型不支持 tool calling（如 DeepSeek 思考模式）
- 模型限额耗尽，返回了空响应

**解决**：切换到支持结构化输出的模型（见「结构化输出.md」）。

---

### 4. oh-agent VM 内访问限制

OpenCode Server 默认监听 `127.0.0.1:4096`（仅 VM 内部）：
- VM 内可直接访问：`http://localhost:4096`
- 宿主机不可直接访问（需走 `orb -m oh-agent curl ...`）
- 后端（FastAPI）在 VM 内，可以直接访问 OpenCode Server，无需额外配置

---

## 环境变量（OpenCodeProvider 支持）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `OPENCODE_BASE_URL` | `http://localhost:4096` | OpenCode Server 地址 |
| `OPENCODE_STRUCTURED_PROVIDER` | `github-copilot` | 结构化输出首选 Provider |
| `OPENCODE_STRUCTURED_MODEL` | `gpt-5-mini` | 结构化输出首选 Model |
| `OPENCODE_STRUCTURED_FALLBACK_PROVIDER` | `opencode` | 结构化输出备用 Provider |
| `OPENCODE_STRUCTURED_FALLBACK_MODEL` | `mimo-v2.5-free` | 结构化输出备用 Model |
