"""Excel 导入预览与确认导入测试。"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import add_templates, build_import_excel


async def test_excel_import_preview_and_confirm(client: AsyncClient, project: dict) -> None:
    project_id = project["id"]
    await add_templates(client, project_id, ["律所签字页"])

    variables_resp = await client.get(f"/api/projects/{project_id}/variables")
    law_firm_name = next(
        item for item in variables_resp.json()["variables"] if item["key"] == "law_firm_name"
    )

    excel_bytes = build_import_excel(
        [
            ("law_firm_name", law_firm_name["label"], "锦天城律师事务所"),
            ("unknown_key", "不存在", "值"),
            ("target_company_name", "目标公司", "非法公司名"),
        ]
    )

    preview_resp = await client.post(
        f"/api/projects/{project_id}/variables/import-preview",
        files={
            "file": (
                "import.xlsx",
                excel_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["summary"]["succeeded"] == 1
    assert preview["summary"]["failed"] == 2

    import_resp = await client.post(
        f"/api/projects/{project_id}/variables/import",
        json={"rows": preview["success"]},
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["summary"]["succeeded"] == 1

    updated_resp = await client.get(f"/api/projects/{project_id}/variables")
    updated = next(
        item for item in updated_resp.json()["variables"] if item["key"] == "law_firm_name"
    )
    assert updated["value"] == "锦天城律师事务所"

    export_resp = await client.get(f"/api/projects/{project_id}/variables/export-template")
    assert export_resp.status_code == 200
    assert (
        export_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(export_resp.content) > 100
