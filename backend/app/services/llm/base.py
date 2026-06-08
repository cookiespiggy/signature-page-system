"""LLM Provider 抽象基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """LLM 服务抽象接口。"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 标识名。"""

    @abstractmethod
    async def create_session(self) -> str:
        """创建会话，返回 session_id。"""

    @property
    def supports_structured_output(self) -> bool:
        """Provider 是否支持原生结构化输出（format/json_schema）。"""
        return False

    @abstractmethod
    async def send_message(
        self,
        prompt: str,
        system: str = "",
        *,
        session_id: str | None = None,
        format: dict | None = None,
    ) -> str:
        """发送 prompt 并返回 LLM 原始文本响应。

        Args:
            prompt: 用户提示。
            system: 系统提示。
            session_id: 会话 ID（可复用）。
            format: 结构化输出格式定义（如 {"type": "json_schema", "schema": {...}}）。
                    支持此参数的 Provider 将返回 JSON 字符串而非自然语言。
        """

    async def health_check(self) -> bool:
        """检查 Provider 是否可用，默认认为可用。"""
        return True
