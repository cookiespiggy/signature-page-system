"""OpenCode Server LLM Provider — v1.16.2 HTTP API 实现。

支持结构化输出（format/json_schema），通过模型 mimo-v2.5-free 原生实现。
当 format 参数传入时自动切换到此模型以获得可靠的 JSON 输出。"""

from __future__ import annotations

import json
import os

import httpx

from app.services.llm.base import LLMProvider

DEFAULT_OPENCODE_BASE_URL = "http://localhost:4096"
DEFAULT_TIMEOUT = 120.0

MODEL_STRUCTURED = "mimo-v2.5-free"
PROVIDER = "opencode"


class OpenCodeProvider(LLMProvider):
    """通过 OpenCode Server REST API 调用 LLM（v1.16.2）。"""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = (base_url or os.getenv("OPENCODE_BASE_URL", DEFAULT_OPENCODE_BASE_URL)).rstrip(
            "/"
        )
        self._timeout = timeout

    @property
    def provider_name(self) -> str:
        return "opencode"

    @property
    def supports_structured_output(self) -> bool:
        """OpenCode 通过 mimo-v2.5-free 模型支持原生结构化输出。"""
        return True

    async def create_session(self) -> str:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/session")
            response.raise_for_status()
            data = response.json()
            session_id = data.get("id") or data.get("session_id")
            if not session_id:
                raise ValueError("OpenCode Server 未返回 session_id")
            return str(session_id)

    async def send_message(
        self,
        prompt: str,
        system: str = "",
        *,
        session_id: str | None = None,
        format: dict | None = None,
    ) -> str:
        sid = session_id or await self.create_session()

        parts: list[dict] = [{"type": "text", "text": prompt}]
        payload: dict = {"parts": parts}

        if system:
            payload["system"] = system

        if format:
            payload["format"] = format
            payload["model"] = {"providerID": PROVIDER, "modelID": MODEL_STRUCTURED}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/session/{sid}/message",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, str):
                return data

            if isinstance(data, dict):
                info = data.get("info", {})

                # 原生结构化输出：info.structured 包含验证后的 JSON
                if isinstance(info, dict) and format:
                    structured = info.get("structured")
                    if structured:
                        return json.dumps(structured, ensure_ascii=False)

                # 普通文本回复：从 parts 中提取
                raw_parts = data.get("parts", [])
                for part in raw_parts:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text", "")
                        if text.strip():
                            return text

                if isinstance(info, dict):
                    for key in ("content", "message", "text", "response"):
                        val = info.get(key)
                        if val:
                            return str(val)

            return str(data)

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/global/health")
                return response.status_code == 200
        except (httpx.HTTPError, OSError):
            return False
