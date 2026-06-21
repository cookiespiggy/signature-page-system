"""AI 调用 Workflow — 替代 ai_service.py 手写重试，使用 Temporal 声明式重试。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities.ai import LLMCallInput, LLMCallResult, call_llm
    from app.temporal.task_queues import AI_CALLS


@dataclass
class AIWorkflowInput:
    """AI Workflow 输入。"""

    scene: str
    prompt: str
    system: str = ""


@dataclass
class AIWorkflowResult:
    """AI Workflow 输出。"""

    response: dict[str, Any]


@workflow.defn
class AIActivityWorkflow:
    """统一 AI 调用 Workflow。

    使用 Temporal 声明式重试替代 ai_service 中的手写 for 循环：
    - 3 次重试 + 指数退避
    - 超时 30 秒
    """

    @workflow.run
    async def run(self, input: AIWorkflowInput) -> AIWorkflowResult:
        result = await workflow.execute_activity(
            call_llm,
            LLMCallInput(
                scene=input.scene,
                prompt=input.prompt,
                system=input.system,
            ),
            task_queue=AI_CALLS,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                backoff_coefficient=2.0,
            ),
        )
        return AIWorkflowResult(response=result.response)
