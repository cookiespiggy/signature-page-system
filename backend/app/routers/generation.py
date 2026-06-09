"""文档生成与下载 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    GeneratedFileResponse,
    GeneratedFileListResponse,
    GenerationStartResponse,
    GenerationStatusResponse,
)
from app.services import generation_service

router = APIRouter(prefix="/api", tags=["generation"])


@router.post(
    "/projects/{project_id}/generate",
    response_model=GenerationStartResponse,
    status_code=202,
)
async def start_generation(
    project_id: int,
    db: Session = Depends(get_db),
) -> GenerationStartResponse:
    task = generation_service.start_generation(db, project_id)
    return GenerationStartResponse(task_id=task.id, status=task.status)


@router.post(
    "/projects/{project_id}/generate/cancel",
    response_model=GenerationStatusResponse,
)
async def cancel_generation(
    project_id: int,
    db: Session = Depends(get_db),
) -> GenerationStatusResponse:
    task = generation_service.cancel_generation(db, project_id)
    return GenerationStatusResponse.model_validate(task)


@router.get(
    "/projects/{project_id}/generate/status",
    response_model=GenerationStatusResponse | None,
)
async def get_generation_status(
    project_id: int,
    db: Session = Depends(get_db),
) -> GenerationStatusResponse | None:
    task = generation_service.get_generation_status(db, project_id)
    if task is None:
        return None
    return GenerationStatusResponse.model_validate(task)


@router.get(
    "/projects/{project_id}/files",
    response_model=GeneratedFileListResponse,
)
async def list_generated_files(
    project_id: int,
    db: Session = Depends(get_db),
) -> GeneratedFileListResponse:
    files = generation_service.list_generated_files(db, project_id)
    return GeneratedFileListResponse(
        files=[
            GeneratedFileResponse(
                id=f.id,
                project_id=f.project_id,
                template_id=f.template_id,
                template_name=f.template.name if f.template else None,
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
    generated = generation_service.get_generated_file(db, file_id)
    path = generation_service.resolve_download_path(generated)
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
    zip_bytes, zip_name = generation_service.build_download_all_zip(db, project_id)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'},
    )
