#!/usr/bin/env bash
cd "$(dirname "$0")"
# 默认使用 Mock LLM Provider，避免依赖 OpenCode Server
# 如需启用 LLM：export LLM_PROVIDER=opencode
export LLM_PROVIDER=mock
nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
echo $!
