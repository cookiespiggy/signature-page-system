"""FastAPI 应用入口。"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import SessionLocal
from app.routers import health, projects, templates
from app.services import template_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        template_service.load_runtime_registry(db)
        template_service.seed_preset_templates(db)
    finally:
        db.close()
    yield
    # Session 4 将在此 shutdown ThreadPoolExecutor


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
