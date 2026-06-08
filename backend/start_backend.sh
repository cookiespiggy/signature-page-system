#!/usr/bin/env bash
cd "$(dirname "$0")"
export LLM_PROVIDER=opencode
nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/uvicorn.log 2>&1 &
echo $!
