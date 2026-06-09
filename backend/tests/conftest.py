"""pytest 公共 fixtures — 隔离测试库 + Mock LLM。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

# 必须在导入 app 之前设置环境变量
_test_root = Path(tempfile.mkdtemp(prefix="junhe_pytest_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_test_root / 'test.db'}"
os.environ["GENERATED_DIR"] = str(_test_root / "generated")
os.environ["LLM_PROVIDER"] = "mock"

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.services import template_service


@pytest.fixture(autouse=True)
def reset_database() -> None:
    """每个测试使用全新 schema 并种子预置模板。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        template_service.load_runtime_registry(db)
        template_service.seed_preset_templates(db)
    finally:
        db.close()
    yield


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def project(client: AsyncClient) -> dict:
    response = await client.post("/api/projects", json={"name": "联调测试项目"})
    assert response.status_code == 201
    return response.json()


async def template_id_by_name(client: AsyncClient, name: str) -> int:
    response = await client.get("/api/templates")
    assert response.status_code == 200
    for item in response.json():
        if item["name"] == name:
            return item["id"]
    raise AssertionError(f"未找到模板: {name}")
