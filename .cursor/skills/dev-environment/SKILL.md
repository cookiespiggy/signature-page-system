---
name: dev-environment
description: >-
  Configures and runs the 签字页管理系统 dev stack on OrbStack oh-agent VM
  with macOS host frontend. Covers .venv cross-platform traps, backend/frontend
  startup, LLM_PROVIDER selection, and post-session process cleanup. Use when
  starting a session, running uvicorn/pytest/alembic, fixing port conflicts,
  or any environment/deployment question for this project.
---

# 开发环境（OrbStack + oh-agent）

## 架构速览

- **后端 / pytest / alembic / OpenCode**：`orb -m oh-agent`（Linux .venv）
- **前端 Vite**：宿主机 macOS（`npm run dev`，代理 `/api` → VM :8000）
- **禁止**在宿主机直接 `uv run` 后端（.venv 是 Linux Python）

## Session 启动检查清单

```
- [ ] .venv 在 VM 内可用（若报 ModuleNotFoundError: python → VM 内 uv sync）
- [ ] OpenCode Server 运行中（仅 opencode 模式需要）
- [ ] 后端 --host 0.0.0.0 --port 8000
- [ ] 前端 VITE_API_PROXY_TARGET 指向 VM IP
```

## 常用命令

```bash
# 重建 .venv（跨平台陷阱后）
orb -m oh-agent bash -lc 'cd backend && rm -rf .venv && uv sync'

# OpenCode Server
orb -m oh-agent bash -lc 'nohup /home/jimmy/.opencode/bin/opencode serve --port 4096 > /dev/null 2>&1 &'

# 后端（默认 opencode）
orb -m oh-agent bash -lc 'cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000'

# 后端（离线 mock）
orb -m oh-agent bash -lc 'cd backend && LLM_PROVIDER=mock uv run uvicorn app.main:app --host 0.0.0.0 --port 8000'

# 前端
cd frontend && npm run dev

# pytest
orb -m oh-agent bash -lc 'cd backend && uv run pytest tests/'

# 迁移
orb -m oh-agent bash -lc 'cd backend && uv run alembic upgrade head'
```

## 联调 / E2E 后必须清理

```bash
orb -m oh-agent bash -lc 'pkill -f "uvicorn app.main:app"'
pkill -f "vite" 2>/dev/null
```

`address already in use` → 先执行清理再重启。

## 场景矩阵（在哪执行）

| 任务 | 位置 |
|------|------|
| uvicorn / pytest / alembic | `orb -m oh-agent` |
| npm run dev / build | 宿主机 |
| git | 宿主机 |
| OpenCode serve | `orb -m oh-agent` |

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `DATABASE_URL` | `sqlite:///./data/junhe.db` | 数据库 |
| `LLM_PROVIDER` | `opencode` | `opencode`/`mock`/`openai` |
| `GENERATED_DIR` | `data/generated` | 生成文件目录 |

## 详细参考

完整踩坑与场景说明见 [reference.md](reference.md)。
