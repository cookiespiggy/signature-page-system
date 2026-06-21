"""LongCat API LLM Provider — OpenAI 兼容接口实现。

LongCat API Platform (https://longcat.chat) 兼容 OpenAI API 格式。
默认模型 LongCat-2.0-Preview，支持 1M token 上下文窗口。
"""

from __future__ import annotations

import os

import httpx

from app.services.llm.base import LLMProvider

DEFAULT_LONGCAT_BASE_URL = "https://api.longcat.chat/openai/v1"
DEFAULT_MODEL = "LongCat-2.0-Preview"
DEFAULT_TIMEOUT = 120.0


class LongCatProvider(LLMProvider):
    """通过 LongCat API (OpenAI 兼容) 调用 LLM。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._api_key = api_key or os.getenv("LONGCAT_API_KEY", "")
        self._base_url = (base_url or os.getenv("LONGCAT_BASE_URL", DEFAULT_LONGCAT_BASE_URL)).rstrip(
            "/"
        )
        self._model = model or os.getenv("LONGCAT_MODEL", DEFAULT_MODEL)
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "longcat"

    async def create_session(self) -> str:
        return "longcat-default"

    async def send_message(
        self,
        prompt: str,
        system: str = "",
        *,
        session_id: str | None = None,
        format: dict | None = None,
    ) -> str:
        if not self._api_key:
            raise ValueError("LONGCAT_API_KEY 未配置")

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            if content is None:
                refusal = data["choices"][0]["message"].get("refusal", "模型拒绝回答")
                raise ValueError(f"LongCat API 返回 refusal: {refusal}")
            return content

    async def health_check(self) -> bool:
        if not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                return response.status_code == 200
        except (httpx.HTTPError, OSError):
            return False
