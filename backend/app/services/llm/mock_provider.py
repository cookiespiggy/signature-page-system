"""Mock LLM Provider — 开发/测试用，返回预设 JSON。"""

from __future__ import annotations

import uuid

from app.services.llm.base import LLMProvider
from app.services.llm.mock_responses import (
    DATA_VALIDATE_MOCK,
    TEMPLATE_PARSE_MOCK,
    VARIABLE_DEDUP_MOCK,
    get_mock_json,
)


def _detect_scene(prompt: str) -> str:
    """根据 prompt 关键词推断 AI 场景。"""
    if "去重" in prompt or "dedup" in prompt.lower() or "合并" in prompt:
        return "variable_dedup"
    if "校验" in prompt or "validate" in prompt.lower():
        return "data_validate"
    if "解析" in prompt or "parse" in prompt.lower() or "占位符" in prompt:
        return "template_parse"
    return "template_parse"


class MockProvider(LLMProvider):
    """返回预设结构化 JSON 的 Mock 实现。"""

    @property
    def provider_name(self) -> str:
        return "mock"

    async def create_session(self) -> str:
        return f"mock-session-{uuid.uuid4().hex[:8]}"

    async def send_message(
        self,
        prompt: str,
        system: str = "",
        *,
        session_id: str | None = None,
        format: dict | None = None,
    ) -> str:
        scene = _detect_scene(f"{system}\n{prompt}")
        return get_mock_json(scene)

    async def health_check(self) -> bool:
        return True

    @staticmethod
    def get_scene_mock(scene: str) -> dict:
        """按场景名获取 Mock 数据字典。"""
        mapping = {
            "template_parse": TEMPLATE_PARSE_MOCK,
            "variable_dedup": VARIABLE_DEDUP_MOCK,
            "data_validate": DATA_VALIDATE_MOCK,
        }
        return mapping.get(scene, TEMPLATE_PARSE_MOCK)
