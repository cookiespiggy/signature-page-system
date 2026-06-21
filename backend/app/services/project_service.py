"""项目业务逻辑。"""

from __future__ import annotations

import os
import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import ProjectNotFoundError
from app.models import GeneratedFile, GenerationTask, Project

GENERATED_DIR = os.getenv("GENERATED_DIR", "data/generated")

ACTIVE_GENERATION_STATUSES = {"pending", "processing"}


def _project_dir(project_id: int) -> Path:
    return Path(GENERATED_DIR) / str(project_id)


def list_projects(db: Session) -> list[Project]:
    stmt = select(Project).order_by(Project.updated_at.desc())
    return list(db.scalars(stmt).all())


def get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise ProjectNotFoundError(f"项目 {project_id} 不存在")
    return project


def create_project(db: Session, name: str) -> Project:
    project = Project(name=name, status="draft")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def update_project(
    db: Session,
    project_id: int,
    *,
    name: str | None = None,
    project_status: str | None = None,
) -> Project:
    project = get_project(db, project_id)
    if name is not None:
        project.name = name
    if project_status is not None:
        project.status = project_status
    db.commit()
    db.refresh(project)
    return project


def _cancel_active_generation_tasks(db: Session, project_id: int) -> None:
    """取消进行中的生成任务（DB 状态更新 + 线程取消信号）。"""
    from app.services import generation_service

    stmt = select(GenerationTask).where(
        GenerationTask.project_id == project_id,
        GenerationTask.status.in_(ACTIVE_GENERATION_STATUSES),
    )
    tasks = list(db.scalars(stmt).all())
    now = datetime.now(UTC).replace(tzinfo=None)
    for task in tasks:
        generation_service.cancel_generation_task(task.id, set_db=False)
        task.status = "cancelled"
        task.cancelled_at = now
    if tasks:
        db.flush()


def _cleanup_generated_files(db: Session, project_id: int) -> None:
    """删除项目关联的物理文件及目录。"""
    stmt = select(GeneratedFile).where(GeneratedFile.project_id == project_id)
    files = list(db.scalars(stmt).all())
    for gf in files:
        path = Path(gf.file_path)
        if path.is_file():
            path.unlink(missing_ok=True)

    project_path = _project_dir(project_id)
    if project_path.exists():
        shutil.rmtree(project_path, ignore_errors=True)


def delete_project(db: Session, project_id: int) -> None:
    """删除项目：先取消生成任务，再清理文件，最后级联删除 DB 记录。"""
    project = get_project(db, project_id)
    _cancel_active_generation_tasks(db, project_id)
    _cleanup_generated_files(db, project_id)
    db.delete(project)
    db.commit()
