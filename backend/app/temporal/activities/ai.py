"""AI 调用 Activities — 封装 LLM 调用（IO 密集）。

设计要点：
  - 使用 call_llm_once()（单次尝试），由 Temporal RetryPolicy 管理重试
  - 避免与 call_llm_structured() 的内置重试形成二重重试
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from temporalio import activity

logger = logging.getLogger(__name__)


@dataclass
class LLMCallInput:
    """LLM 调用输入。"""

    scene: str
    prompt: str
    system: str = ""


@dataclass
class LLMCallResult:
    """LLM 调用结果。"""

    response: dict[str, Any]


@activity.defn
async def call_llm(input: LLMCallInput) -> LLMCallResult:
    """调用 LLM 并返回结构化结果。

    使用 call_llm_once()（单次尝试），由 Temporal 的 RetryPolicy 管理重试，
    不引入二重重试。
    """
    from app.services.ai_service import call_llm_once
    from app.schemas import TemplateParseResult, VariableDedupResult, DataValidateResult

    scene_schema_map = {
        "template_parse": TemplateParseResult,
        "variable_dedup": VariableDedupResult,
        "data_validate": DataValidateResult,
    }
    schema_class = scene_schema_map.get(input.scene)
    if schema_class is None:
        raise ValueError(f"未知的 AI 场景: {input.scene}")

    result = await call_llm_once(
        input.prompt,
        schema_class,
        system=input.system,
        scene=input.scene,
    )
    return LLMCallResult(response=result.model_dump())
