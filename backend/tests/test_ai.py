"""AI 场景 Mock 集成测试。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient

from app.services import ai_service
from app.services.template_service import APP_DIR
from tests.helpers import add_templates, save_sample_variables


async def test_template_parse_returns_trust_levels(client: AsyncClient) -> None:
    template_path = APP_DIR / "templates" / "law_firm_signing_page.docx"
    with template_path.open("rb") as file_obj:
        response = await client.post(
            "/api/templates/parse",
            files={
                "file": (
                    "law_firm_signing_page.docx",
                    file_obj,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ai_used"] is True
    assert len(body["variables"]) >= 1
    assert all("trust_level" in item for item in body["variables"])


async def test_ai_dedup_mock(client: AsyncClient, project: dict) -> None:
    project_id = project["id"]
    await add_templates(
        client,
        project_id,
        ["律所签字页", "自然人股东签字页"],
    )

    response = await client.post(f"/api/projects/{project_id}/variables/ai-dedup")
    assert response.status_code == 200
    body = response.json()
    assert body["ai_used"] is True
    assert isinstance(body["ai_suggestions"], list)
    assert isinstance(body["alias_suggestions"], list)


async def test_ai_validate_mock(client: AsyncClient, project: dict) -> None:
    project_id = project["id"]
    await add_templates(client, project_id, ["律所签字页"])
    await save_sample_variables(client, project_id)

    response = await client.post(f"/api/projects/{project_id}/variables/ai-validate")
    assert response.status_code == 200
    body = response.json()
    assert body["ai_used"] is True
    assert isinstance(body["issues"], list)
    assert "regex_issues" in body
    assert "ai_issues" in body


async def test_ai_dedup_degraded(client: AsyncClient, project: dict) -> None:
    project_id = project["id"]
    await add_templates(client, project_id, ["律所签字页"])

    with patch(
        "app.services.variable_service.ai_service.suggest_variable_dedup",
        new_callable=AsyncMock,
        side_effect=ai_service.AIServiceUnavailableError(ai_service.AI_UNAVAILABLE_MSG),
    ):
        response = await client.post(f"/api/projects/{project_id}/variables/ai-dedup")

    assert response.status_code == 200
    body = response.json()
    assert body["ai_used"] is False
    assert body["message"] == ai_service.AI_UNAVAILABLE_MSG


async def test_ai_validate_degraded_returns_regex_issues(
    client: AsyncClient,
    project: dict,
) -> None:
    project_id = project["id"]
    await add_templates(client, project_id, ["律所签字页"])

    with patch(
        "app.services.variable_service.ai_service.validate_variable_data",
        new_callable=AsyncMock,
        side_effect=ai_service.AIServiceUnavailableError(ai_service.AI_UNAVAILABLE_MSG),
    ):
        response = await client.post(f"/api/projects/{project_id}/variables/ai-validate")

    assert response.status_code == 200
    body = response.json()
    assert body["ai_used"] is False
    assert body["message"] == ai_service.AI_UNAVAILABLE_MSG
    assert isinstance(body["issues"], list)
