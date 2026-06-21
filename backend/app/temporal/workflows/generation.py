"""文档生成 Workflow — 替代 ThreadPoolExecutor + threading.Event。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.temporal.activities.generation import (
        RenderInput,
        cancel_generation_in_db,
        cleanup_partial_files,
        fail_generation,
        finalize_generation,
        initialize_generation,
        render_template,
        update_progress,
    )
    from app.temporal.task_queues import DOCUMENT_GENERATION


@dataclass
class GenerationWorkflowInput:
    """Workflow 输入参数。"""

    project_id: int


@dataclass
class GenerationProgress:
    """Workflow 进度查询结果。"""

    completed_count: int = 0
    total_count: int = 0
    status: str = "pending"
    files: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Workflow 最终结果。"""

    status: str
    completed_count: int
    total_count: int
    files: list[str]


@workflow.defn
class DocumentGenerationWorkflow:
    """文档生成 Workflow。

    用 Temporal 替代原有的 ThreadPoolExecutor + threading.Event 方案：
    - Signal: cancel — 取消生成
    - Query: progress — 查询进度
    - Activity: render_template — 逐模板渲染
    """

    def __init__(self) -> None:
        self._cancelled = False
        self._completed_count = 0
        self._total_count = 0
        self._status = "pending"
        self._files: list[str] = []
        self._failed_templates: list[str] = []

    @workflow.run
    async def run(self, input: GenerationWorkflowInput) -> GenerationResult:
        project_id = input.project_id
        workflow.logger.info("开始生成项目 %d 的文档", project_id)

        try:
            # 1. 初始化：设置状态、加载变量上下文
            init_result = await workflow.execute_activity(
                initialize_generation,
                project_id,
                task_queue=DOCUMENT_GENERATION,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2),
            )

            self._total_count = init_result.total_count
            self._status = "processing"
            template_ids = init_result.template_ids
            template_names = init_result.template_names
            context = init_result.context

            # 2. 逐模板渲染
            for index, template_id in enumerate(template_ids):
                if self._cancelled:
                    break

                try:
                    result = await workflow.execute_activity(
                        render_template,
                        RenderInput(
                            project_id=project_id,
                            template_id=template_id,
                            context=context,
                        ),
                        task_queue=DOCUMENT_GENERATION,
                        start_to_close_timeout=timedelta(minutes=5),
                        retry_policy=RetryPolicy(maximum_attempts=1),
                    )
                except Exception as exc:
                    name = template_names[index] if index < len(template_names) else f"模板#{template_id}"
                    self._failed_templates.append(name)
                    workflow.logger.error(
                        "模板「%s」渲染失败: %s", name, exc
                    )
                    continue

                if result:
                    self._completed_count = index + 1
                    self._files.append(result.file_path)

                    # 更新 DB 进度
                    await workflow.execute_activity(
                        update_progress,
                        args=[project_id, self._completed_count],
                        task_queue=DOCUMENT_GENERATION,
                        start_to_close_timeout=timedelta(seconds=10),
                    )

            # 3. 构建失败信息
            partial_fail_msg = None
            if self._failed_templates:
                partial_fail_msg = (
                    f"以下模板生成失败: {', '.join(self._failed_templates)}"
                    f"（{self._completed_count}/{self._total_count} 个成功）"
                )

            if self._cancelled:
                await workflow.execute_activity(
                    cancel_generation_in_db,
                    args=[project_id, self._completed_count],
                    task_queue=DOCUMENT_GENERATION,
                    start_to_close_timeout=timedelta(seconds=10),
                )
                await workflow.execute_activity(
                    cleanup_partial_files,
                    project_id,
                    task_queue=DOCUMENT_GENERATION,
                    start_to_close_timeout=timedelta(seconds=30),
                )
                self._status = "cancelled"
            else:
                await workflow.execute_activity(
                    finalize_generation,
                    args=[project_id, self._completed_count, partial_fail_msg],
                    task_queue=DOCUMENT_GENERATION,
                    start_to_close_timeout=timedelta(seconds=10),
                )
                self._status = "completed"

        except asyncio.CancelledError:
            # Temporal 层面的取消（如 workflow.cancel()）
            workflow.logger.info("Workflow 被取消，执行清理")
            await workflow.execute_activity(
                cancel_generation_in_db,
                args=[project_id, self._completed_count],
                task_queue=DOCUMENT_GENERATION,
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.execute_activity(
                cleanup_partial_files,
                project_id,
                task_queue=DOCUMENT_GENERATION,
                start_to_close_timeout=timedelta(seconds=30),
            )
            self._status = "cancelled"
            raise

        except Exception as exc:
            workflow.logger.error("生成任务异常: %s", exc)
            await workflow.execute_activity(
                fail_generation,
                args=[project_id, str(exc), self._completed_count],
                task_queue=DOCUMENT_GENERATION,
                start_to_close_timeout=timedelta(seconds=10),
            )
            self._status = "failed"

        return GenerationResult(
            status=self._status,
            completed_count=self._completed_count,
            total_count=self._total_count,
            files=self._files,
        )

    @workflow.signal
    def cancel(self) -> None:
        """取消生成（外部通过 signal 调用）。"""
        self._cancelled = True

    @workflow.query
    def progress(self) -> GenerationProgress:
        """查询当前进度。"""
        return GenerationProgress(
            completed_count=self._completed_count,
            total_count=self._total_count,
            status=self._status,
            files=list(self._files),
        )
