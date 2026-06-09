"""端到端主流程：创建 → 选模板 → 填变量 → 生成 → 下载。"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    LAW_FIRM_SAMPLE_VALUES,
    add_templates,
    save_sample_variables,
    wait_for_generation,
)


async def test_full_workflow(client: AsyncClient) -> None:
    create_resp = await client.post("/api/projects", json={"name": "E2E 全流程"})
    assert create_resp.status_code == 201
    project_id = create_resp.json()["id"]

    await add_templates(
        client,
        project_id,
        ["律所签字页", "机构股东签字页"],
    )

    variables_resp = await client.get(f"/api/projects/{project_id}/variables")
    assert variables_resp.status_code == 200
    variables = variables_resp.json()["variables"]
    assert any(item["key"] == "target_company_name" for item in variables)
    assert sum(1 for item in variables if item["key"] == "target_company_name") == 1

    merged_values = {
        **LAW_FIRM_SAMPLE_VALUES,
        "institutional_shareholder_name": "测试机构股东有限责任公司",
        "authorized_representative_name": "赵六",
        "meeting_year": "2026",
        "meeting_session": "第一次",
    }
    await save_sample_variables(client, project_id, merged_values)

    validate_resp = await client.post(f"/api/projects/{project_id}/variables/ai-validate")
    assert validate_resp.status_code == 200

    start_resp = await client.post(f"/api/projects/{project_id}/generate")
    assert start_resp.status_code == 202

    final_status = await wait_for_generation(client, project_id, timeout_seconds=45.0)
    assert final_status["status"] == "completed"
    assert final_status["total_count"] == 2

    files_resp = await client.get(f"/api/projects/{project_id}/files")
    assert len(files_resp.json()["files"]) == 2

    delete_resp = await client.delete(f"/api/projects/{project_id}")
    assert delete_resp.status_code == 204
