"""Temporal Worker 启动脚本。

运行方式：
    cd backend && uv run python -m app.temporal.worker
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from app.temporal.activities.ai import call_llm
from app.temporal.activities.generation import (
    cancel_generation_in_db,
    cleanup_partial_files,
    fail_generation,
    finalize_generation,
    initialize_generation,
    render_template,
    update_progress,
)
from app.temporal.client import get_client
from app.temporal.task_queues import AI_CALLS, DOCUMENT_GENERATION
from app.temporal.workflows.ai import AIActivityWorkflow
from app.temporal.workflows.generation import DocumentGenerationWorkflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    client = await get_client()
    logger.info("已连接 Temporal Server")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as activity_executor:
        # 文档生成 Worker
        gen_worker = Worker(
            client,
            task_queue=DOCUMENT_GENERATION,
            workflows=[DocumentGenerationWorkflow],
            activities=[
                initialize_generation,
                render_template,
                update_progress,
                finalize_generation,
                fail_generation,
                cancel_generation_in_db,
                cleanup_partial_files,
            ],
            activity_executor=activity_executor,
        )

        # AI 调用 Worker
        ai_worker = Worker(
            client,
            task_queue=AI_CALLS,
            workflows=[AIActivityWorkflow],
            activities=[call_llm],
            activity_executor=activity_executor,
        )

        logger.info("Worker 已启动，监听队列: %s, %s", DOCUMENT_GENERATION, AI_CALLS)
        await asyncio.gather(gen_worker.run(), ai_worker.run())


if __name__ == "__main__":
    asyncio.run(main())
