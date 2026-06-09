"""项目 CRUD 与删除级联测试。"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import GeneratedFile, GenerationTask, Project, ProjectTemplate, Variable


async def test_health(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_project_crud(client: AsyncClient) -> None:
    create_resp = await client.post("/api/projects", json={"name": "CRUD 项目"})
    assert create_resp.status_code == 201
    project = create_resp.json()
    project_id = project["id"]

    get_resp = await client.get(f"/api/projects/{project_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "CRUD 项目"

    update_resp = await client.put(
        f"/api/projects/{project_id}",
        json={"name": "已更新项目"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "已更新项目"

    list_resp = await client.get("/api/projects")
    assert list_resp.status_code == 200
    assert any(item["id"] == project_id for item in list_resp.json())

    delete_resp = await client.delete(f"/api/projects/{project_id}")
    assert delete_resp.status_code == 204

    missing_resp = await client.get(f"/api/projects/{project_id}")
    assert missing_resp.status_code == 404


async def test_delete_project_cascade(
    client: AsyncClient,
    project: dict,
) -> None:
    from tests.conftest import template_id_by_name
    from tests.helpers import add_templates, save_sample_variables

    project_id = project["id"]
    law_firm_id = await template_id_by_name(client, "律所签字页")
    await add_templates(client, project_id, ["律所签字页"])
    await save_sample_variables(client, project_id)

    start_resp = await client.post(f"/api/projects/{project_id}/generate")
    assert start_resp.status_code == 202

    delete_resp = await client.delete(f"/api/projects/{project_id}")
    assert delete_resp.status_code == 204

    db = SessionLocal()
    try:
        assert db.scalar(select(func.count()).select_from(Project)) == 0
        assert (
            db.scalar(
                select(func.count()).select_from(ProjectTemplate).where(
                    ProjectTemplate.project_id == project_id
                )
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count()).select_from(Variable).where(
                    Variable.project_id == project_id
                )
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count()).select_from(GenerationTask).where(
                    GenerationTask.project_id == project_id
                )
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count()).select_from(GeneratedFile).where(
                    GeneratedFile.project_id == project_id
                )
            )
            == 0
        )
    finally:
        db.close()

    templates_resp = await client.get("/api/templates")
    assert any(item["id"] == law_firm_id for item in templates_resp.json())
