"""AI 编排服务 — 封装 LLM 调用、超时、重试与降级。

架构分层：
  - call_llm_once():        单次调用尝试，供 Temporal Activity 直接使用（Temporal 管理重试）
  - call_llm_structured():  带手写重试循环的完整调用，供 USE_TEMPORAL=false 时使用

支持双模式：
  - USE_TEMPORAL=true: 通过 Temporal Workflow 编排 LLM 调用（声明式重试 + Web UI 可见性）
  - USE_TEMPORAL=false (默认): 直接调用 LLM Provider（手写重试循环）
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.services.llm.factory import get_llm_provider
from app.services.llm.mock_provider import MockProvider

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

LLM_TIMEOUT_SECONDS = 30.0
MAX_RETRIES = 3

AI_UNAVAILABLE_MSG = "AI 服务不可用，请使用手工操作或稍后重试"

USE_TEMPORAL = os.getenv("USE_TEMPORAL", "false").lower() in {"true", "1", "yes"}


async def _call_via_temporal(
    scene: str,
    prompt: str,
    schema: type[T],
    *,
    system: str = "",
) -> T | None:
    """通过 Temporal Workflow 调用 LLM，失败时返回 None 供调用方降级。"""
    try:
        from app.temporal.client import get_client
        from app.temporal.task_queues import AI_CALLS
        from app.temporal.workflows.ai import AIActivityWorkflow, AIWorkflowInput

        client = await get_client()
        workflow_id = f"ai-{scene}-{uuid.uuid4().hex[:8]}"
        handle = await client.start_workflow(
            AIActivityWorkflow.run,
            AIWorkflowInput(scene=scene, prompt=prompt, system=system),
            id=workflow_id,
            task_queue=AI_CALLS,
        )
        result = await handle.result()
        return schema.model_validate(result.response)
    except Exception as exc:
        logger.warning("Temporal 调用失败，降级到直接 LLM 调用: %s", exc)
        return None


class AIServiceUnavailableError(Exception):
    """AI 服务重试耗尽后的降级错误。"""


def _extract_json(text: str) -> str:
    """从 LLM 响应中提取 JSON 字符串。"""
    text = text.strip()
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        return code_block.group(1).strip()
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


async def call_llm_once(
    prompt: str,
    schema: type[T],
    *,
    system: str = "",
    scene: str | None = None,
) -> T:
    """单次 LLM 调用尝试（无重试），供 Temporal Activity 使用。

    Temporal Activity 调用此函数，由 Temporal 的 RetryPolicy 管理重试，
    避免 call_llm_structured 内部的二重重试。
    """
    provider = get_llm_provider()

    if isinstance(provider, MockProvider) and scene:
        mock_data = MockProvider.get_scene_mock(scene)
        return schema.model_validate(mock_data)

    json_schema_str = json.dumps(schema.model_json_schema(), ensure_ascii=False)

    if provider.supports_structured_output:
        raw = await provider.send_message(
            prompt,
            system=system,
            format={"type": "json_schema", "schema": schema.model_json_schema()},
        )
        data = json.loads(raw)
        return schema.model_validate(data)
    else:
        raw = await provider.send_message(
            prompt,
            system=_build_structured_system(system, json_schema_str),
        )
        json_str = _extract_json(raw)
        data = json.loads(json_str)
        return schema.model_validate(data)


async def call_llm_structured(
    prompt: str,
    schema: type[T],
    *,
    system: str = "",
    scene: str | None = None,
) -> T:
    """
    调用 LLM 并解析为 Pydantic 模型（带手写重试循环）。

    供非 Temporal 路径（USE_TEMPORAL=false）使用。
    耗尽后抛出 AIServiceUnavailableError。
    """
    last_error: str | None = None
    current_prompt = prompt
    current_system = system

    json_schema_str = json.dumps(schema.model_json_schema(), ensure_ascii=False)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await call_llm_once(
                current_prompt, schema, system=current_system, scene=scene,
            )
        except (ValidationError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            logger.warning("LLM 响应解析失败 (attempt %d/%d): %s", attempt, MAX_RETRIES, last_error)
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


# ---------------------------------------------------------------------------
# 三个 AI 场景方法
# ---------------------------------------------------------------------------


async def parse_template_variables(
    template_text: str,
) -> dict[str, Any]:
    """AI-1: 智能模板解析。"""
    from app.schemas import TemplateParseResult

    system = "你是一个签字页文档解析专家。"
    prompt = (
        f"请解析以下 Word 模板内容中的占位符变量（形如 {{variable_key}}）。\n\n"
        f"对每个变量请提供：\n"
        f"- key: 英文标识（snake_case，如 target_company_name）\n"
        f"- label: 中文显示名（如 目标公司名称）\n"
        f"- category: 分类（company / lawyer / shareholder / meeting / document / date / other）\n"
        f"- data_type: 数据类型（text / date / company_name / id_number / person_name）\n"
        f"- required: 是否必填\n"
        f"- is_multiple: 是否允许多值（如经办律师可能有多个）\n"
        f"- confidence: 提取置信度（0~1，综合考量占位符直译程度 + 上下文清晰度）\n"
        f"- evidence_list: 从模板原文中提取该变量的依据片段列表（如具体段落文本）\n"
        f"- risk_note: 提取风险说明（如：变量名过于通用、原文中可能出现简称、或歧义需要人工确认）\n\n"
        f"模板内容：\n{template_text}"
    )

    if USE_TEMPORAL:
        result = await _call_via_temporal("template_parse", prompt, TemplateParseResult, system=system)
        if result is not None:
            return result.model_dump()

    result = await call_llm_structured(
        prompt, TemplateParseResult, system=system, scene="template_parse",
    )
    return result.model_dump()


async def suggest_variable_dedup(
    variables: list[dict[str, Any]],
) -> dict[str, Any]:
    """AI-2: 变量去重建议。"""
    from app.schemas import VariableDedupResult

    system = "你是一个签字页变量去重专家。"
    prompt = (
        "请分析以下变量列表，找出语义相同的变量并给出合并建议。\n\n"
        "【规则】\n"
        "1. 仅合并语义确信的相同变量（如 label 完全一致、或高度近似）\n"
        "2. 每条建议必须提供 confidence（0~1）、evidence_list 和 risk_note\n"
        "3. confidence<0.7 的建议不要输出\n"
        "4. evidence_list 列出判断依据的具体片段（如变量 label、category、出现位置等）\n"
        "5. risk_note 说明合并可能带来的风险，如：跨模板合并后需检查所有引用模板\n"
        "6. 只返回 JSON，不要其他内容\n\n"
        f"【Variables】\n{json.dumps(variables, ensure_ascii=False)}"
    )

    if USE_TEMPORAL:
        result = await _call_via_temporal("variable_dedup", prompt, VariableDedupResult, system=system)
        if result is not None:
            return result.model_dump()
    result = await call_llm_structured(
        prompt, VariableDedupResult, system=system, scene="variable_dedup",
    )
    return result.model_dump()


async def validate_variable_data(
    variables: list[dict[str, Any]],
    validation_rules: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """AI-3: 语义交叉校验（不代替格式校验）。

    定位：格式校验（regex）由 _run_regex_validation() 确定性实现，
    AI-3 只做正则做不到的语义一致性检查：
    - 跨字段角色冲突（同一人出现在"经办律师"和"自然人股东"）
    - 日期逻辑矛盾（签署日期 vs 会议年份）
    - 实体名称一致性（目标公司 vs 机构股东）
    - 跨模板一致性问题
    - 明显的业务逻辑反常
    """
    from app.schemas import DataValidateResult

    system = "你是一个签字页数据的语义校验专家。"

    # 构造辅助信息：按 category 分组，帮助 LLM 识别跨字段关系
    by_category: dict[str, list[dict[str, Any]]] = {}
    for v in variables:
        cat = v.get("category", "other")
        by_category.setdefault(cat, []).append(v)

    category_hint_lines = []
    for cat, items in by_category.items():
        keys = ", ".join(f"{i['key']}({i.get('label','')})" for i in items)
        category_hint_lines.append(f"  {cat}: {keys}")

    prompt = (
        "你是一个签字页数据的语义校验专家。\n\n"
        "你的任务是检查变量之间的语义一致性（格式由系统自动校验，不要报告格式问题）。\n\n"
        "请检查以下方面：\n"
        "1. 角色冲突：同一人的姓名出现在不同角色字段（如「经办律师」=「自然人股东」）\n"
        "2. 日期逻辑：签署日期与会议年份/次数是否矛盾\n"
        "3. 名称一致性：目标公司与机构股东等关联实体的名称关系是否合理\n"
        "4. 跨模板一致：同一语义的变量在不同模板中的值是否矛盾\n"
        "5. 其他明显的业务逻辑反常\n\n"
        "禁止事项：\n"
        "- 不要做格式校验（格式已由系统完成）\n"
        "- 不要对单个字段的值做语义判断（如「这个名字不常见」「这个日期在将来」）\n"
        "- 没有明显的语义问题时，不要强行编造问题\n\n"
        "每条结果必须包含：\n"
        "- level: error（确定有问题，必须修正）或 warning（建议确认）\n"
        "- variable_key: 涉及的主变量 key\n"
        "- message: 问题描述\n"
        "- suggestion: 修正建议\n"
        "- confidence: 0~1\n"
        "- evidence_list: 判断依据的具体片段\n"
        "- risk_note: 风险说明\n\n"
        "【变量分组（按 category）】\n"
        f"{chr(10).join(category_hint_lines)}\n\n"
        "【变量明细】\n"
        f"{json.dumps(variables, ensure_ascii=False, indent=2)}"
    )

    if USE_TEMPORAL:
        result = await _call_via_temporal("data_validate", prompt, DataValidateResult, system=system)
        if result is not None:
            return result.model_dump()
    result = await call_llm_structured(
        prompt, DataValidateResult, system=system, scene="data_validate",
    )
    return result.model_dump()
