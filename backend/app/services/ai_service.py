"""AI 编排服务 — 封装 LLM 调用、超时、重试与降级。"""

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.services.llm.factory import get_llm_provider
from app.services.llm.mock_provider import MockProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

LLM_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3

AI_UNAVAILABLE_MSG = "AI 服务不可用，请使用手工操作或稍后重试"


class AIServiceUnavailableError(Exception):
    """AI 服务重试耗尽后的降级错误。"""


def _extract_json(text: str) -> str:
    """从 LLM 响应中提取 JSON 字符串。"""
    text = text.strip()
    # 尝试提取 ```json ... ``` 代码块
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        return code_block.group(1).strip()
    # 尝试提取首个 JSON 对象/数组
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start >= 0:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == start_char:
                    depth += 1
                elif ch == end_char:
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
    return text


async def call_llm_structured(
    prompt: str,
    schema: type[T],
    *,
    system: str = "",
    scene: str | None = None,
) -> T:
    """
    调用 LLM 并解析为 Pydantic 模型。

    策略：
    - Provider 支持原生结构化输出（如 OpenCode + mimo-v2.5-free）：
      直接发送 format/json_schema，跳过 prompt 嵌入 Schema，重试逻辑简化。
    - Provider 不支持（如 Mock/OpenAI + DeepSeek）：
      在 system prompt 中嵌入 JSON Schema，附加重试与降级。
    - 耗尽后抛出 AIServiceUnavailableError。
    """
    provider = get_llm_provider()
    last_error: str | None = None
    current_prompt = prompt
    current_system = system

    json_schema_str = json.dumps(schema.model_json_schema(), ensure_ascii=False)
    use_native = provider.supports_structured_output

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Mock Provider 可直接返回预设数据（跳过重试循环中的网络调用）
            if isinstance(provider, MockProvider) and scene:
                mock_data = MockProvider.get_scene_mock(scene)
                return schema.model_validate(mock_data)

            if use_native:
                raw = await provider.send_message(
                    current_prompt,
                    system=current_system,
                    format={"type": "json_schema", "schema": schema.model_json_schema()},
                )
                data = json.loads(raw)
                return schema.model_validate(data)
            else:
                raw = await provider.send_message(
                    current_prompt,
                    system=_build_structured_system(current_system, json_schema_str),
                )
                json_str = _extract_json(raw)
                data = json.loads(json_str)
                return schema.model_validate(data)

        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            logger.warning("LLM 响应解析失败 (attempt %d/%d): %s", attempt, MAX_RETRIES, last_error)
            if not use_native:
                current_prompt = (
                    f"{prompt}\n\n"
                    f"[系统提示] 上次返回格式不正确，请严格返回符合以下 Schema 的 JSON。\n"
                    f"Schema:\n{json_schema_str}\n"
                    f"错误信息: {last_error}"
                )
        except Exception as exc:
            last_error = str(exc)
            logger.warning("LLM 调用失败 (attempt %d/%d): %s", attempt, MAX_RETRIES, last_error)
            if attempt < MAX_RETRIES:
                current_prompt = (
                    f"{prompt}\n\n[系统提示] 上次调用失败: {last_error}。请重试并返回有效 JSON。"
                )

    raise AIServiceUnavailableError(AI_UNAVAILABLE_MSG)


def _build_structured_system(system: str, json_schema: str) -> str:
    """在 system prompt 中嵌入 JSON Schema 指导。"""
    parts = [system] if system else []
    parts.append(
        "你必须严格按照以下 JSON Schema 返回数据。只返回 JSON 对象本身，"
        "不要 Markdown 代码块标记，不要额外说明。"
    )
    parts.append(f"JSON Schema:\n{json_schema}")
    return "\n\n".join(parts)


# --- 三个 AI 场景占位方法（Session 2/3 完善业务逻辑）---


async def parse_template_variables(template_text: str) -> dict:
    """AI-1: 智能模板解析。"""
    from app.schemas import TemplateParseResult

    system = "你是一个签字页文档解析专家。"
    prompt = f"请解析以下 Word 模板内容中的占位符变量：\n\n{template_text}"
    result = await call_llm_structured(
        prompt,
        TemplateParseResult,
        system=system,
        scene="template_parse",
    )
    return result.model_dump()


async def suggest_variable_dedup(variables: list[dict]) -> dict:
    """AI-2: 变量去重建议。"""
    from app.schemas import VariableDedupResult

    system = "你是一个签字页变量去重专家。"
    prompt = f"请分析以下变量列表，给出合并建议：\n\n{json.dumps(variables, ensure_ascii=False)}"
    result = await call_llm_structured(
        prompt,
        VariableDedupResult,
        system=system,
        scene="variable_dedup",
    )
    return result.model_dump()


async def validate_variable_data(variables: list[dict], validation_rules: dict | None = None) -> dict:
    """AI-3: 数据校验。"""
    from app.schemas import DataValidateResult

    rules = validation_rules or {}
    system = "你是一个签字页数据校验专家。"
    prompt = (
        f"请校验以下变量数据：\n\n"
        f"{json.dumps(variables, ensure_ascii=False)}\n\n"
        f"校验规则：\n{json.dumps(rules, ensure_ascii=False)}"
    )
    result = await call_llm_structured(
        prompt,
        DataValidateResult,
        system=system,
        scene="data_validate",
    )
    return result.model_dump()
