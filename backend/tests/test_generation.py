"""文档异步生成流程测试。"""

from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import (
    add_templates,
    save_sample_variables,
    wait_for_generation,
)


async def test_generation_flow(client: AsyncClient, project: dict) -> None:
    project_id = project["id"]
    await add_templates(client, project_id, ["律所签字页"])
    await save_sample_variables(client, project_id)

    start_resp = await client.post(f"/api/projects/{project_id}/generate")
    assert start_resp.status_code == 202
    task = start_resp.json()
    assert task["status"] in {"pending", "processing"}

    final_status = await wait_for_generation(client, project_id)
    assert final_status["status"] == "completed"
    assert final_status["completed_count"] == final_status["total_count"]
    assert len(final_status["template_progress"]) == 1
    assert final_status["template_progress"][0]["status"] == "completed"
    assert len(final_status["logs"]) >= 2
    assert any("生成完成" in entry["message"] for entry in final_status["logs"])

    files_resp = await client.get(f"/api/projects/{project_id}/files")
    assert files_resp.status_code == 200
    files = files_resp.json()["files"]
    assert len(files) == 1
    assert files[0]["status"] == "completed"
    assert files[0]["template_category"] is not None

    download_resp = await client.get(f"/api/files/{files[0]['id']}/download")
    assert download_resp.status_code == 200
    assert (
        download_resp.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(download_resp.content) > 1000

    zip_resp = await client.get(f"/api/projects/{project_id}/download-all")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"
    assert len(zip_resp.content) > 1000
