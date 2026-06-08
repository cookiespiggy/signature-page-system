"""根据环境变量创建 LLM Provider 实例。"""

from __future__ import annotations

import os

from app.services.llm.base import LLMProvider
from app.services.llm.mock_provider import MockProvider
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.opencode_provider import OpenCodeProvider

_provider_instance: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """获取全局 LLM Provider 单例（按 LLM_PROVIDER 环境变量）。"""
    global _provider_instance
    if _provider_instance is None:
        _provider_instance = create_llm_provider()
    return _provider_instance


def create_llm_provider(provider: str | None = None) -> LLMProvider:
    """根据名称创建 Provider，默认读取 LLM_PROVIDER 环境变量。"""
    name = (provider or os.getenv("LLM_PROVIDER", "mock")).lower().strip()
    if name == "opencode":
        return OpenCodeProvider()
    if name == "openai":
        return OpenAIProvider()
    return MockProvider()


def reset_llm_provider() -> None:
    """重置单例（测试用）。"""
    global _provider_instance
    _provider_instance = None
