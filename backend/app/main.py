"""FastAPI 应用入口。"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal
from app.routers import generation, health, projects, templates, variables
from app.services import generation_service, template_service

logger = logging.getLogger(__name__)

USE_TEMPORAL = os.getenv("USE_TEMPORAL", "false").lower() in {"true", "1", "yes"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB 初始化（模板加载、预置种子）
    db = SessionLocal()
    try:
        template_service.load_runtime_registry(db)
        template_service.seed_preset_templates(db)
    finally:
        db.close()

    # Temporal Client 初始化（仅 API 端连接，Worker 独立进程运行）
    if USE_TEMPORAL:
        from app.temporal.client import get_client
        await get_client()
        logger.info("Temporal 模式已启用 (USE_TEMPORAL=true)")

    yield

    # 清理
    if USE_TEMPORAL:
        from app.temporal.client import close_client
        await close_client()
    generation_service.shutdown_executor()


app = FastAPI(
    title="签字页管理系统",
    description="律师事务所签字页 Word 文档生成 MVP",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(projects.router)
app.include_router(templates.router)
app.include_router(variables.router)
app.include_router(generation.router)
