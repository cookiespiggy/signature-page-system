# OpenCode Server — 完整参考

> 源文档：`docs/knowledge-base/OpenCode-Server.md`

## 安装路径

- `/home/jimmy/.opencode/bin/opencode`（v1.16.2）
- 重装：`orb -m oh-agent curl -fsSL https://opencode.ai/install | bash`

## 查询已连接 Provider

```bash
orb -m oh-agent curl -s http://localhost:4096/provider | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('connected:', d['connected'])
"
```

## 端到端 LLM 验证（写文件，勿用 python -c）

```bash
cat > backend/test_llm_tmp.py << 'EOF'
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

orb -m oh-agent bash -lc 'cd backend && uv run python test_llm_tmp.py'
rm backend/test_llm_tmp.py
```

## 免费模型限额排查

```bash
SID=$(orb -m oh-agent curl -s -X POST http://localhost:4096/session | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
orb -m oh-agent curl -s -m 30 -X POST "http://localhost:4096/session/$SID/message" \
  -H 'Content-Type: application/json' \
  -d '{"parts":[{"type":"text","text":"hi"}],"model":{"providerID":"opencode","modelID":"mimo-v2.5-free"}}'
# 30s 无响应 → 限额耗尽，换 gpt-5-mini
```
