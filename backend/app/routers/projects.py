"""项目 CRUD API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.exceptions import ProjectNotFoundError
from app.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectResponse])
async def list_projects(db: Session = Depends(get_db)) -> list[ProjectResponse]:
    return project_service.list_projects(db)


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    return project_service.create_project(db, body.name)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        return project_service.get_project(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    body: ProjectUpdate,
    db: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        return project_service.update_project(
            db,
            project_id,
            name=body.name,
            project_status=body.status,
        )
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> None:
    try:
        project_service.delete_project(db, project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
