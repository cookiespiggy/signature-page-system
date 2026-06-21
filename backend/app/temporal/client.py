"""Temporal Client 单例 — 全局复用。"""

from __future__ import annotations

from temporalio.client import Client

from app.temporal.config import TEMPORAL_ADDRESS, TEMPORAL_NAMESPACE

_client: Client | None = None


async def get_client() -> Client:
    """获取或创建 Temporal Client 单例。"""
    global _client
    if _client is None:
        _client = await Client.connect(
            TEMPORAL_ADDRESS,
            namespace=TEMPORAL_NAMESPACE,
        )
    return _client


async def close_client() -> None:
    """关闭 Client 连接（应用退出时调用）。"""
    global _client
    _client = None
