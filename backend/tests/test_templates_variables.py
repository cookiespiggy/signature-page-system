"""模板选择、变量去重、乐观锁、模板刷新测试。"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import select

from app.database import SessionLocal
from app.models import Template, Variable
from tests.helpers import add_templates


async def test_template_dedup_on_select(client: AsyncClient, project: dict) -> None:
    project_id = project["id"]
    await add_templates(
        client,
        project_id,
        ["律所签字页", "自然人股东签字页"],
    )

    response = await client.get(f"/api/projects/{project_id}/variables")
    assert response.status_code == 200
    variables = response.json()["variables"]
    keys = [item["key"] for item in variables]

    assert keys.count("target_company_name") == 1
    assert keys.count("signing_date") == 1

    shared = next(item for item in variables if item["key"] == "target_company_name")
    assert len(shared["source_template_ids"]) == 2


async def test_optimistic_lock_partial_success(client: AsyncClient, project: dict) -> None:
    project_id = project["id"]
    await add_templates(client, project_id, ["律所签字页"])

    list_resp = await client.get(f"/api/projects/{project_id}/variables")
    variables = list_resp.json()["variables"]
    target = next(item for item in variables if item["key"] == "law_firm_name")

    stale_resp = await client.put(
        f"/api/projects/{project_id}/variables",
        json={
            "variables": [
                {
                    "key": "law_firm_name",
                    "value": "过期写入",
                    "updated_at": "2000-01-01T00:00:00",
                },
                {
                    "key": "law_firm_director",
                    "value": "张三",
                    "updated_at": next(
                        item["updated_at"]
                        for item in variables
                        if item["key"] == "law_firm_director"
                    ),
                },
            ]
        },
    )
    assert stale_resp.status_code == 200
    body = stale_resp.json()
    assert body["summary"]["succeeded"] == 1
    assert body["summary"]["failed"] == 1
    assert any("已被其他操作修改" in item["message"] for item in body["errors"])

    ok_resp = await client.put(
        f"/api/projects/{project_id}/variables",
        json={
            "variables": [
                {
                    "key": "law_firm_name",
                    "value": "君合律师事务所",
                    "updated_at": target["updated_at"],
                }
            ]
        },
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["summary"]["succeeded"] == 1


async def test_remove_template_cleans_variables(client: AsyncClient, project: dict) -> None:
    from tests.conftest import template_id_by_name

    project_id = project["id"]
    await add_templates(
        client,
        project_id,
        ["律所签字页", "自然人股东签字页"],
    )

    natural_id = await template_id_by_name(client, "自然人股东签字页")
    remove_resp = await client.delete(
        f"/api/projects/{project_id}/templates/{natural_id}",
    )
    assert remove_resp.status_code == 204

    variables_resp = await client.get(f"/api/projects/{project_id}/variables")
    keys = [item["key"] for item in variables_resp.json()["variables"]]
    assert "natural_shareholder_name" not in keys
    assert "target_company_name" in keys


async def test_template_refresh_diff(client: AsyncClient, project: dict) -> None:
    from tests.conftest import template_id_by_name

    project_id = project["id"]
    await add_templates(client, project_id, ["律所签字页"])
    template_id = await template_id_by_name(client, "律所签字页")

    db = SessionLocal()
    try:
        template = db.scalar(select(Template).where(Template.id == template_id))
        assert template is not None
        variables = list(template.variables_json or [])
        variables.append(
            {
                "key": "custom_refresh_marker",
                "label": "刷新测试变量",
                "category": "other",
                "data_type": "text",
                "required": False,
                "is_multiple": False,
            }
        )
        template.variables_json = variables
        template.variable_count = len(variables)
        template.version += 1
        db.commit()
    finally:
        db.close()

    refresh_resp = await client.post(
        f"/api/projects/{project_id}/templates/{template_id}/refresh",
    )
    assert refresh_resp.status_code == 200
    result = refresh_resp.json()
    assert result["added"] == 1
    assert result["removed"] == 0
    assert result["kept"] >= 1

    variables_resp = await client.get(f"/api/projects/{project_id}/variables")
    keys = [item["key"] for item in variables_resp.json()["variables"]]
    assert "custom_refresh_marker" in keys


async def test_preset_template_cannot_delete(client: AsyncClient) -> None:
    from tests.conftest import template_id_by_name

    template_id = await template_id_by_name(client, "律所签字页")
    response = await client.delete(f"/api/templates/{template_id}")
    assert response.status_code == 403
