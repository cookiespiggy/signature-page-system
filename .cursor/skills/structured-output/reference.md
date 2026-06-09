# 结构化输出 — 完整参考

> 源文档：`docs/knowledge-base/结构化输出.md`

## curl 验证结构化输出

```bash
SID=$(orb -m oh-agent curl -s -X POST http://localhost:4096/session | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
orb -m oh-agent curl -s -m 60 -X POST "http://localhost:4096/session/$SID/message" \
  -H 'Content-Type: application/json' \
  -d '{
    "parts":[{"type":"text","text":"返回一个包含 ok 字段的 JSON"}],
    "model":{"providerID":"github-copilot","modelID":"gpt-5-mini"},
    "format":{"type":"json_schema","schema":{"type":"object","properties":{"ok":{"type":"boolean"}},"required":["ok"]}}
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print('structured=', d['info'].get('structured'))"
```

## 环境变量覆盖

```bash
OPENCODE_STRUCTURED_PROVIDER=github-copilot
OPENCODE_STRUCTURED_MODEL=gpt-5-mini
OPENCODE_STRUCTURED_FALLBACK_PROVIDER=opencode
OPENCODE_STRUCTURED_FALLBACK_MODEL=mimo-v2.5-free
```

## 响应特征（原生成功）

```json
{
  "info": {
    "finish": "tool-calls",
    "structured": { "...符合 schema..." }
  }
}
```
