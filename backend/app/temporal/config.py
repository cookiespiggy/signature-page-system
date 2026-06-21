"""Temporal 连接配置 — 从环境变量读取。"""

from __future__ import annotations

import os

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost")
TEMPORAL_PORT = int(os.getenv("TEMPORAL_PORT", "7233"))
TEMPORAL_ADDRESS = f"{TEMPORAL_HOST}:{TEMPORAL_PORT}"
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
