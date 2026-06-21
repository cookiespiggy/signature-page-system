"""文档生成与下载 API。

支持双模式运行：
- USE_TEMPORAL=true: 通过 Temporal Workflow 编排生成任务
- USE_TEMPORAL=false (默认): 使用传统 ThreadPoolExecutor（兼容期）
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import (
    ActiveTaskExistsError,
    NoActiveTaskError,
    NoTemplatesSelectedError,
    ProjectNotFoundError,
    TemplateFileMissingError,
)
from app.schemas import (
    GeneratedFileResponse,
    GeneratedFileListResponse,
    GenerationStartResponse,
    GenerationStatusResponse,
)
from app.services import generation_service

router = APIRouter(prefix="/api", tags=["generation"])

USE_TEMPORAL = os.getenv("USE_TEMPORAL", "false").lower() in {"true", "1", "yes"}


def _workflow_id(project_id: int) -> str:
    return f"doc-gen-project-{project_id}-{uuid.uuid4().hex[:8]}"


@router.post(
    "/projects/{project_id}/generate",
    response_model=GenerationStartResponse,
    status_code=202,
)
async def start_generation(
    project_id: int,
    db: Session = Depends(get_db),
) -> GenerationStartResponse:
    try:
        if USE_TEMPORAL:
            return await _start_generation_temporal(project_id, db)
        task = generation_service.start_generation(db, project_id)
        return GenerationStartResponse(task_id=task.id, status=task.status)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except NoTemplatesSelectedError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except TemplateFileMissingError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except ActiveTaskExistsError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


async def _start_generation_temporal(
    project_id: int, db: Session
) -> GenerationStartResponse:
    """通过 Temporal Workflow 启动生成。"""
    from app.services.project_service import get_project
    from app.models import GenerationTask, ProjectTemplate, Template
    from sqlalchemy import select

    get_project(db, project_id)

    # 检查模板
    stmt = (
        select(Template)
        .join(ProjectTemplate, ProjectTemplate.template_id == Template.id)
        .where(ProjectTemplate.project_id == project_id)
        .order_by(ProjectTemplate.id)
    )
    templates = list(db.scalars(stmt).all())
    if not templates:
        raise NoTemplatesSelectedError("请先为项目选择至少一个模板")

    from pathlib import Path
    for template in templates:
        path = Path(template.file_path or "")
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.is_file():
            raise TemplateFileMissingError(f"模板「{template.name}」文件缺失，无法生成")

    # 检查活跃任务
    active_stmt = select(GenerationTask).where(
        GenerationTask.project_id == project_id,
        GenerationTask.status.in_({"pending", "processing"}),
    )
    if db.scalar(active_stmt):
        raise ActiveTaskExistsError("该项目已有进行中的生成任务")

    # 创建 DB 任务记录（pending 状态）
    task = GenerationTask(
        project_id=project_id,
        status="pending",
        total_count=len(templates),
        completed_count=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 启动 Temporal Workflow
    from app.temporal.client import get_client
    from app.temporal.workflows.generation import (
        DocumentGenerationWorkflow,
        GenerationWorkflowInput,
    )
    from app.temporal.task_queues import DOCUMENT_GENERATION

    client = await get_client()
    await client.start_workflow(
        DocumentGenerationWorkflow.run,
        GenerationWorkflowInput(project_id=project_id),
        id=_workflow_id(project_id),
        task_queue=DOCUMENT_GENERATION,
    )
    return GenerationStartResponse(task_id=task.id, status=task.status)


@router.post(
    "/projects/{project_id}/generate/cancel",
    response_model=GenerationStatusResponse,
)
async def cancel_generation(
    project_id: int,
    db: Session = Depends(get_db),
) -> GenerationStatusResponse:
    try:
        if USE_TEMPORAL:
            return await _cancel_generation_temporal(project_id, db)
        task = generation_service.cancel_generation(db, project_id)
        payload = generation_service.build_generation_status_response(db, task)
        return GenerationStatusResponse.model_validate(payload)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except NoActiveTaskError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


async def _cancel_generation_temporal(
    project_id: int, db: Session
) -> GenerationStatusResponse:
    """通过 Temporal Signal 取消生成。"""
    from app.temporal.client import get_client
    from app.temporal.workflows.generation import DocumentGenerationWorkflow
    from app.models import GenerationTask
    from sqlalchemy import select

    stmt = select(GenerationTask).where(
        GenerationTask.project_id == project_id,
        GenerationTask.status.in_({"pending", "processing"}),
    )
    task = db.scalar(stmt)
    if task is None:
        raise NoActiveTaskError("没有进行中的生成任务")

    # 发送 cancel signal 到所有匹配的 workflow
    client = await get_client()
    async for wf in client.list_workflows(
        query=f'WorkflowType="DocumentGenerationWorkflow" AND ExecutionStatus="Running"'
    ):
        if f"project-{project_id}" in wf.workflow_id:
            handle = client.get_workflow_handle_for(
                DocumentGenerationWorkflow, wf.workflow_id
            )
            await handle.signal(DocumentGenerationWorkflow.cancel)

    # 同时更新 DB 状态（防止 workflow 还没处理 signal 时用户查询）
    from datetime import UTC, datetime
    now = datetime.now(UTC).replace(tzinfo=None)
    task.status = "cancelled"
    task.cancelled_at = now
    db.commit()

    from app.models import Project
    project = db.get(Project, project_id)
    if project and project.status == "generating":
        project.status = "draft"
        db.commit()

    db.refresh(task)
    payload = generation_service.build_generation_status_response(db, task)
    return GenerationStatusResponse.model_validate(payload)


@router.get(
    "/projects/{project_id}/generate/status",
    response_model=GenerationStatusResponse | None,
)
async def get_generation_status(
    project_id: int,
    db: Session = Depends(get_db),
) -> GenerationStatusResponse | None:
    try:
        task = generation_service.get_generation_status(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    if task is None:
        return None
    payload = generation_service.build_generation_status_response(db, task)
    return GenerationStatusResponse.model_validate(payload)


@router.get(
    "/projects/{project_id}/files",
    response_model=GeneratedFileListResponse,
)
async def list_generated_files(
    project_id: int,
    db: Session = Depends(get_db),
) -> GeneratedFileListResponse:
    try:
        files = generation_service.list_generated_files(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return GeneratedFileListResponse(
        files=[
            GeneratedFileResponse(
                id=f.id,
                project_id=f.project_id,
                template_id=f.template_id,
                template_name=f.template.name if f.template else None,
                template_category=f.template.category if f.template else None,
                file_path=f.file_path,
                status=f.status,
                created_at=f.created_at,
            )
            for f in files
        ]
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    try:
        generated = generation_service.get_generated_file(db, file_id)
        path = generation_service.resolve_download_path(generated)
    except NoActiveTaskError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return FileResponse(
        path=path,
        filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/projects/{project_id}/download-all")
async def download_all(
    project_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        zip_bytes, zip_name = generation_service.build_download_all_zip(db, project_id)
    except (ProjectNotFoundError, NoActiveTaskError) as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )
