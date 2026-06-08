"""OpenCode Server LLM Provider — v1.16.2 HTTP API 实现。

支持结构化输出（format/json_schema）。
默认使用 github-copilot/gpt-5-mini 进行结构化输出；
若失败则自动 fallback 到 opencode/mimo-v2.5-free。"""

from __future__ import annotations

import json
import logging
import os

import httpx

from app.services.llm.base import LLMProvider

DEFAULT_OPENCODE_BASE_URL = "http://localhost:4096"
DEFAULT_TIMEOUT = 120.0

DEFAULT_STRUCTURED_PROVIDER = "github-copilot"
DEFAULT_STRUCTURED_MODEL = "gpt-5-mini"
DEFAULT_STRUCTURED_FALLBACK_PROVIDER = "opencode"
DEFAULT_STRUCTURED_FALLBACK_MODEL = "mimo-v2.5-free"

logger = logging.getLogger(__name__)


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
        self._structured_provider = os.getenv(
            "OPENCODE_STRUCTURED_PROVIDER", DEFAULT_STRUCTURED_PROVIDER
        ).strip()
        self._structured_model = os.getenv(
            "OPENCODE_STRUCTURED_MODEL", DEFAULT_STRUCTURED_MODEL
        ).strip()
        self._structured_fallback_provider = os.getenv(
            "OPENCODE_STRUCTURED_FALLBACK_PROVIDER",
            DEFAULT_STRUCTURED_FALLBACK_PROVIDER,
        ).strip()
        self._structured_fallback_model = os.getenv(
            "OPENCODE_STRUCTURED_FALLBACK_MODEL",
            DEFAULT_STRUCTURED_FALLBACK_MODEL,
        ).strip()

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

        candidates = self._build_model_candidates(format=format)

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            last_error: Exception | None = None
            for index, model in enumerate(candidates):
                payload = self._build_payload(prompt=prompt, system=system, format=format, model=model)
                try:
                    response = await client.post(
                        f"{self._base_url}/session/{sid}/message",
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    return self._extract_response_text(data=data, format=format)
                except Exception as exc:
                    last_error = exc
                    if index >= len(candidates) - 1:
                        break
                    next_model = candidates[index + 1]
                    from_model = "default/default"
                    if model:
                        from_model = f"{model['providerID']}/{model['modelID']}"
                    to_model = "default/default"
                    if next_model:
                        to_model = f"{next_model['providerID']}/{next_model['modelID']}"
                    logger.warning(
                        "OpenCode 模型调用失败，切换到备用模型重试: %s -> %s, error=%s",
                        from_model,
                        to_model,
                        str(exc),
                    )
            if last_error:
                raise last_error
            raise RuntimeError("OpenCode 调用失败：未找到可用模型")

    def _build_model_candidates(self, *, format: dict | None) -> list[dict[str, str] | None]:
        if not format:
            return [None]

        raw_candidates = [
            {
                "providerID": self._structured_provider or DEFAULT_STRUCTURED_PROVIDER,
                "modelID": self._structured_model or DEFAULT_STRUCTURED_MODEL,
            },
            {
                "providerID": self._structured_fallback_provider or DEFAULT_STRUCTURED_FALLBACK_PROVIDER,
                "modelID": self._structured_fallback_model or DEFAULT_STRUCTURED_FALLBACK_MODEL,
            },
        ]

        deduped: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for candidate in raw_candidates:
            key = (candidate["providerID"], candidate["modelID"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)
        return deduped

    def _build_payload(
        self,
        *,
        prompt: str,
        system: str,
        format: dict | None,
        model: dict[str, str] | None,
    ) -> dict:
        parts: list[dict] = [{"type": "text", "text": prompt}]
        payload: dict = {"parts": parts}
        if system:
            payload["system"] = system
        if format:
            payload["format"] = format
        if model:
            payload["model"] = model
        return payload

    def _extract_response_text(self, *, data: object, format: dict | None) -> str:
        if isinstance(data, str):
            return data

        if isinstance(data, dict):
            info = data.get("info", {})

            if isinstance(info, dict) and format:
                structured = info.get("structured")
                if structured:
                    return json.dumps(structured, ensure_ascii=False)
                raise ValueError("OpenCode 未返回结构化字段 info.structured")

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
