"""模板管理 API。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import (
    PresetTemplateDeleteForbidden,
    ProjectTemplateNotLinkedError,
    TemplateNotFoundError,
    TemplateReferencedError,
)
from app.schemas import (
    ProjectTemplateResponse,
    ProjectTemplateSelect,
    TemplateCreate,
    TemplateParseResponse,
    TemplateRefreshResponse,
    TemplateResponse,
    TemplateUpdate,
    TemplateVariableDefinition,
)
from app.services import template_service

router = APIRouter(prefix="/api", tags=["templates"])


def _to_template_response(template) -> TemplateResponse:
    return TemplateResponse.model_validate(template)


def _to_project_template_response(pt, db: Session) -> ProjectTemplateResponse:
    template = template_service.get_template(db, pt.template_id)
    return ProjectTemplateResponse(
        id=pt.id,
        project_id=pt.project_id,
        template_id=pt.template_id,
        template_version=pt.template_version,
        variables_snapshot_json=pt.variables_snapshot_json,
        needs_refresh=pt.template_version < template.version,
        latest_template_version=template.version,
    )


@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(db: Session = Depends(get_db)) -> list[TemplateResponse]:
    return [_to_template_response(t) for t in template_service.list_templates(db)]


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> TemplateResponse:
    try:
        return _to_template_response(template_service.get_template(db, template_id))
    except TemplateNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post("/templates/parse", response_model=TemplateParseResponse)
async def parse_template(
    file: UploadFile = File(...),
) -> TemplateParseResponse:
    result = await template_service.parse_template_file(file)
    return TemplateParseResponse(**result)


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str | None = Form(None),
    category: str = Form("other"),
    tags: str = Form("[]"),
    applicable_scenarios: str | None = Form(None),
    variables_json: str = Form("[]"),
    register_custom_variables: bool = Form(True),
    db: Session = Depends(get_db),
) -> TemplateResponse:
    saved_path = await template_service.save_upload_file(
        file, template_service.CUSTOM_TEMPLATES_DIR
    )
    parsed_tags = json.loads(tags) if tags else []
    parsed_vars = [
        TemplateVariableDefinition.model_validate(v).model_dump()
        for v in json.loads(variables_json or "[]")
    ]
    template = template_service.create_template(
        db,
        name=name,
        description=description,
        category=category,
        tags=parsed_tags,
        applicable_scenarios=applicable_scenarios,
        variables_json=parsed_vars,
        file_path=str(saved_path),
        register_custom=register_custom_variables,
    )
    return _to_template_response(template)


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int,
    file: UploadFile | None = File(None),
    name: str | None = Form(None),
    description: str | None = Form(None),
    category: str | None = Form(None),
    tags: str | None = Form(None),
    applicable_scenarios: str | None = Form(None),
    variables_json: str | None = Form(None),
    register_custom_variables: bool = Form(True),
    db: Session = Depends(get_db),
) -> TemplateResponse:
    saved_path: str | None = None
    if file is not None and file.filename:
        path = await template_service.save_upload_file(
            file, template_service.CUSTOM_TEMPLATES_DIR
        )
        saved_path = str(path)

    parsed_tags = json.loads(tags) if tags else None
    parsed_vars = None
    if variables_json is not None:
        parsed_vars = [
            TemplateVariableDefinition.model_validate(v).model_dump()
            for v in json.loads(variables_json or "[]")
        ]

    template = template_service.update_template(
        db,
        template_id,
        name=name,
        description=description,
        category=category,
        tags=parsed_tags,
        applicable_scenarios=applicable_scenarios,
        variables_json=parsed_vars,
        file_path=saved_path,
        register_custom=register_custom_variables,
    )
    return _to_template_response(template)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
) -> None:
    try:
        template_service.delete_template(db, template_id)
    except TemplateNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    except PresetTemplateDeleteForbidden as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e))
    except TemplateReferencedError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.get(
    "/projects/{project_id}/templates",
    response_model=list[ProjectTemplateResponse],
)
async def list_project_templates(
    project_id: int,
    db: Session = Depends(get_db),
) -> list[ProjectTemplateResponse]:
    pts = template_service.list_project_templates(db, project_id)
    return [_to_project_template_response(pt, db) for pt in pts]


@router.post(
    "/projects/{project_id}/templates",
    response_model=list[ProjectTemplateResponse],
    status_code=201,
)
async def add_project_templates(
    project_id: int,
    body: ProjectTemplateSelect,
    db: Session = Depends(get_db),
) -> list[ProjectTemplateResponse]:
    added = template_service.add_templates_to_project(db, project_id, body.template_ids)
    return [_to_project_template_response(pt, db) for pt in added]


@router.delete("/projects/{project_id}/templates/{template_id}", status_code=204)
async def remove_project_template(
    project_id: int,
    template_id: int,
    db: Session = Depends(get_db),
) -> None:
    try:
        template_service.remove_template_from_project(db, project_id, template_id)
    except ProjectTemplateNotLinkedError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.post(
    "/projects/{project_id}/templates/{template_id}/refresh",
    response_model=TemplateRefreshResponse,
)
async def refresh_project_template(
    project_id: int,
    template_id: int,
    db: Session = Depends(get_db),
) -> TemplateRefreshResponse:
    try:
        result = template_service.refresh_project_template(db, project_id, template_id)
        return TemplateRefreshResponse(**result)
    except ProjectTemplateNotLinkedError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
