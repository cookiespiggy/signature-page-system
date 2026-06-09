"""测试辅助函数。"""

from __future__ import annotations

import asyncio
import io
import time
from typing import Any

from httpx import AsyncClient
from openpyxl import Workbook

LAW_FIRM_SAMPLE_VALUES: dict[str, str] = {
    "target_company_name": "测试股份有限公司",
    "law_firm_name": "君合律师事务所",
    "law_firm_director": "张三",
    "handling_lawyer_1": "李四",
    "handling_lawyer_2": "王五",
    "exchange_name": "上海证券交易所",
    "document_type": "法律意见书",
    "target_investor_type": "合格投资者",
    "signing_date": "2026年6月9日",
}


async def add_templates(
    client: AsyncClient,
    project_id: int,
    template_names: list[str],
) -> None:
    from tests.conftest import template_id_by_name

    ids = [await template_id_by_name(client, name) for name in template_names]
    response = await client.post(
        f"/api/projects/{project_id}/templates",
        json={"template_ids": ids},
    )
    assert response.status_code == 201, response.text


async def save_sample_variables(
    client: AsyncClient,
    project_id: int,
    values: dict[str, str] | None = None,
) -> None:
    values = values or LAW_FIRM_SAMPLE_VALUES
    variables_resp = await client.get(f"/api/projects/{project_id}/variables")
    assert variables_resp.status_code == 200
    variables = variables_resp.json()["variables"]

    payload = []
    for var in variables:
        key = var["key"]
        if key not in values:
            continue
        payload.append(
            {
                "key": key,
                "value": values[key],
                "updated_at": var["updated_at"],
            }
        )

    response = await client.put(
        f"/api/projects/{project_id}/variables",
        json={"variables": payload},
    )
    assert response.status_code == 200, response.text
    assert response.json()["summary"]["failed"] == 0


def build_import_excel(rows: list[tuple[str, str, str]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["变量标识(key)", "变量名称(label)", "值(value)"])
    for row in rows:
        ws.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


async def wait_for_generation(
    client: AsyncClient,
    project_id: int,
    *,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = await client.get(f"/api/projects/{project_id}/generate/status")
        assert response.status_code == 200
        data = response.json()
        if data and data.get("status") in {"completed", "failed", "cancelled"}:
            return data
        await asyncio.sleep(0.5)
    raise TimeoutError(f"生成任务超时（>{timeout_seconds}s）")
