"""变量 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import (
    ExcelFormatError,
    ExcelParseError,
    ProjectNotFoundError,
)
from app.schemas import (
    AiDedupResponse,
    AiValidateResponse,
    ApplyDedupRequest,
    ApplyDedupResponse,
    BatchOperationResponse,
    ImportConfirmRequest,
    VariableListResponse,
    VariableResponse,
    VariableSaveRequest,
)
from app.services import variable_service

router = APIRouter(prefix="/api/projects", tags=["variables"])


@router.get("/{project_id}/variables", response_model=VariableListResponse)
async def list_variables(
    project_id: int,
    db: Session = Depends(get_db),
) -> VariableListResponse:
    try:
        variables = variable_service.list_variables(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return VariableListResponse(
        variables=[VariableResponse(**v) for v in variables]
    )


@router.put("/{project_id}/variables", response_model=BatchOperationResponse)
async def save_variables(
    project_id: int,
    body: VariableSaveRequest,
    db: Session = Depends(get_db),
) -> BatchOperationResponse:
    try:
        items = [item.model_dump() for item in body.variables]
        result = variable_service.save_variables(db, project_id, items)
        return BatchOperationResponse(**result)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/{project_id}/variables/ai-dedup", response_model=AiDedupResponse)
async def ai_dedup_variables(
    project_id: int,
    db: Session = Depends(get_db),
) -> AiDedupResponse:
    try:
        result = await variable_service.ai_dedup_suggestions(db, project_id)
        return AiDedupResponse(**result)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/{project_id}/variables/apply-dedup", response_model=ApplyDedupResponse)
async def apply_dedup_variables(
    project_id: int,
    body: ApplyDedupRequest,
    db: Session = Depends(get_db),
) -> ApplyDedupResponse:
    try:
        suggestions = [s.model_dump() for s in body.suggestions]
        result = variable_service.apply_dedup_suggestions(db, project_id, suggestions)
        return ApplyDedupResponse(**result)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/{project_id}/variables/ai-validate", response_model=AiValidateResponse)
async def ai_validate_variables(
    project_id: int,
    db: Session = Depends(get_db),
) -> AiValidateResponse:
    try:
        result = await variable_service.ai_validate_variables(db, project_id)
        return AiValidateResponse(**result)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post(
    "/{project_id}/variables/import-preview",
    response_model=BatchOperationResponse,
)
async def import_preview(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> BatchOperationResponse:
    try:
        result = await variable_service.import_preview(db, project_id, file)
        return BatchOperationResponse(**result)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except ExcelFormatError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except ExcelParseError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/{project_id}/variables/import", response_model=BatchOperationResponse)
async def import_variables(
    project_id: int,
    body: ImportConfirmRequest,
    db: Session = Depends(get_db),
) -> BatchOperationResponse:
    try:
        result = variable_service.import_variables(db, project_id, body.rows)
        return BatchOperationResponse(**result)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get("/{project_id}/variables/export-template")
async def export_template(
    project_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        content = variable_service.export_template_excel(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="project_{project_id}_template.xlsx"'
        },
    )


@router.get("/{project_id}/variables/export")
async def export_variables(
    project_id: int,
    db: Session = Depends(get_db),
) -> Response:
    try:
        content = variable_service.export_variables_excel(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="project_{project_id}_variables.xlsx"'
        },
    )
