# 开发环境 — 完整参考

> 源文档：`docs/knowledge-base/环境配置.md`

## .venv 跨平台陷阱

| 在哪创建 | 在哪能用 |
|---------|---------|
| macOS 宿主机 | 仅 macOS |
| oh-agent VM | 仅 Linux VM |
| macOS 创建后到 VM 用 | ❌ `ModuleNotFoundError: No module named 'python'` |

`orb -m oh-agent` 在 VM 内执行命令，使用共享文件系统上的 Linux `.venv/`。

## LLM Provider 选择

| LLM_PROVIDER | 适用场景 |
|-------------|---------|
| `opencode`（默认） | 日常开发，需 OpenCode Server |
| `mock` | 离线 / CI，无外部 LLM |
| `openai` | 需 `OPENAI_API_KEY` |

## 进程清理详情

联调结束后检查：
```bash
orb -m oh-agent bash -lc 'pgrep -af uvicorn'
orb -m oh-agent bash -lc 'ss -tlnp | grep :8000 || echo "port 8000 free"'
lsof -i :5173 2>/dev/null || echo "port 5173 free"
```

OpenCode Server（:4096）可保留，VM 重启后再按需启动。
