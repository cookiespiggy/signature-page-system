"""文档生成 Activities — 非确定性操作（DB、文件 I/O）。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from temporalio import activity

from app.database import SessionLocal
from app.models import GeneratedFile, GenerationTask, Project, ProjectTemplate, Template, Variable
from app.services.project_service import GENERATED_DIR
from app.services.render_utils import (
    add_audit_log,
    build_render_context,
    project_output_dir,
    render_one_template as _render_one_shared,
)

logger = logging.getLogger(__name__)


@dataclass
class RenderInput:
    """渲染单模板的输入参数。"""
    project_id: int
    template_id: int
    context: dict[str, Any]


@dataclass
class RenderResult:
    """渲染单模板的结果。"""
    file_path: str
    file_id: int
    template_name: str


@dataclass
class InitResult:
    """初始化结果。"""
    template_ids: list[int]
    template_names: list[str]
    total_count: int
    context: dict[str, Any]


@activity.defn
def initialize_generation(project_id: int) -> InitResult:
    """初始化生成任务：设置状态、加载变量上下文。"""
    db = SessionLocal()
    try:
        task = db.scalar(
            select(GenerationTask)
            .where(GenerationTask.project_id == project_id)
            .order_by(GenerationTask.created_at.desc())
            .limit(1)
        )
        if task is None:
            raise RuntimeError(f"项目 {project_id} 没有生成任务")

        task.status = "processing"
        project = db.get(Project, project_id)
        if project:
            project.status = "generating"

        # 加载模板列表（ID + 名称）
        stmt = (
            select(Template.id, Template.name)
            .join(ProjectTemplate, ProjectTemplate.template_id == Template.id)
            .where(ProjectTemplate.project_id == project_id)
            .order_by(ProjectTemplate.id)
        )
        rows = list(db.execute(stmt).all())
        template_ids = [row[0] for row in rows]
        template_names = [row[1] for row in rows]

        # 加载变量并构建渲染上下文
        variables = list(
            db.scalars(select(Variable).where(Variable.project_id == project_id)).all()
        )
        context = build_render_context(variables)

        task.total_count = len(template_ids)
        db.commit()

        return InitResult(
            template_ids=template_ids,
            template_names=template_names,
            total_count=len(template_ids),
            context=context,
        )
    finally:
        db.close()


@activity.defn
def render_template(input: RenderInput) -> RenderResult:
    """渲染单个模板为 Word 文件。"""
    db = SessionLocal()
    try:
        template = db.get(Template, input.template_id)
        if template is None:
            raise RuntimeError(f"模板 {input.template_id} 不存在")

        task = db.scalar(
            select(GenerationTask)
            .where(GenerationTask.project_id == input.project_id)
            .order_by(GenerationTask.created_at.desc())
            .limit(1)
        )
        task_id = task.id if task else None

        add_audit_log(
            db, project_id=input.project_id, action="template_started",
            message=f"模板「{template.name}」开始生成（模板版本 v{template.version}）",
            generation_task_id=task_id,
            details={"template_id": template.id, "template_name": template.name, "template_version": template.version},
        )

        generated = _render_one_shared(
            db,
            project_id=input.project_id,
            template=template,
            context=input.context,
            output_dir=project_output_dir(input.project_id),
            generation_task_id=task_id,
        )

        filename = generated.file_path.split("/")[-1] if "/" in generated.file_path else generated.file_path
        add_audit_log(
            db, project_id=input.project_id, action="template_completed",
            message=f"模板「{template.name}」生成完成（模板版本 v{template.version}） → {filename}",
            generation_task_id=task_id,
            details={
                "template_id": template.id, "template_name": template.name,
                "template_version": template.version, "file_id": generated.id,
                "filename": filename,
            },
        )
        db.commit()

        activity.heartbeat(generated.id)
        logger.info("模板「%s」渲染完成: %s", template.name, generated.file_path)

        return RenderResult(
            file_path=generated.file_path,
            file_id=generated.id,
            template_name=template.name,
        )
    finally:
        db.close()


@activity.defn
def update_progress(project_id: int, completed_count: int) -> None:
    """更新生成进度。"""
    db = SessionLocal()
    try:
        task = db.scalar(
            select(GenerationTask)
            .where(GenerationTask.project_id == project_id)
            .order_by(GenerationTask.created_at.desc())
            .limit(1)
        )
        if task:
            task.completed_count = completed_count
            db.commit()
    finally:
        db.close()


@activity.defn
def finalize_generation(project_id: int, completed_count: int, error_message: str | None = None) -> None:
    """完成生成任务：更新状态为 completed，如有部分失败记录错误信息。"""
    db = SessionLocal()
    try:
        task = db.scalar(
            select(GenerationTask)
            .where(GenerationTask.project_id == project_id)
            .order_by(GenerationTask.created_at.desc())
            .limit(1)
        )
        if task is None:
            return
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)
        task.status = "completed"
        task.completed_count = completed_count
        task.error_message = error_message
        task.updated_at = now
        task.completed_at = now

        project = db.get(Project, project_id)
        if project:
            project.status = "completed"
        add_audit_log(
            db, project_id=project_id, action="completed",
            message=error_message or f"全部 {completed_count}/{completed_count} 个文件生成完成",
            generation_task_id=task.id,
            details={"completed_count": completed_count, "error_message": error_message},
        )
        db.commit()
    finally:
        db.close()


@activity.defn
def fail_generation(project_id: int, error_message: str, completed_count: int) -> None:
    """标记生成任务为失败。"""
    db = SessionLocal()
    try:
        task = db.scalar(
            select(GenerationTask)
            .where(GenerationTask.project_id == project_id)
            .order_by(GenerationTask.created_at.desc())
            .limit(1)
        )
        if task is None:
            return
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)
        task.status = "failed"
        task.error_message = error_message
        task.completed_count = completed_count
        task.updated_at = now

        project = db.get(Project, project_id)
        if project and project.status == "generating":
            project.status = "draft"
        add_audit_log(
            db, project_id=project_id, action="failed",
            message=f"生成失败: {error_message}",
            generation_task_id=task.id,
            details={"error": error_message, "completed_count": completed_count},
        )
        db.commit()
    finally:
        db.close()


@activity.defn
def cancel_generation_in_db(project_id: int, completed_count: int) -> None:
    """取消生成任务（DB 状态更新）。"""
    db = SessionLocal()
    try:
        task = db.scalar(
            select(GenerationTask)
            .where(GenerationTask.project_id == project_id)
            .order_by(GenerationTask.created_at.desc())
            .limit(1)
        )
        if task is None:
            return
        from datetime import UTC, datetime

        now = datetime.now(UTC).replace(tzinfo=None)
        task.status = "cancelled"
        task.completed_count = completed_count
        task.cancelled_at = now
        task.updated_at = now

        project = db.get(Project, project_id)
        if project and project.status == "generating":
            project.status = "draft"
        add_audit_log(
            db, project_id=project_id, action="cancelled",
            message=f"生成任务已取消，已完成 {completed_count}/{task.total_count} 个文件",
            generation_task_id=task.id,
            details={"completed_count": completed_count, "total_count": task.total_count},
        )
        db.commit()
    finally:
        db.close()


@activity.defn
def cleanup_partial_files(project_id: int) -> None:
    """清理取消时已生成的部分文件。"""
    output_dir = Path(GENERATED_DIR) / str(project_id)
    if not output_dir.exists():
        return
    for tmp_file in output_dir.glob(".tmp_*"):
        tmp_file.unlink(missing_ok=True)
