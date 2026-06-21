"""文档生成 Activities — 非确定性操作（DB、文件 I/O）。"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from sqlalchemy import select
from sqlalchemy.orm import Session
from temporalio import activity

from app.database import SessionLocal
from app.models import GeneratedFile, GenerationTask, Project, ProjectTemplate, Template, Variable
from app.services.project_service import GENERATED_DIR

logger = logging.getLogger(__name__)

_UNSAFE_FILENAME = re.compile(r"[^\w\-_.一-龥]+")
_BASE_KEY_PATTERN = re.compile(r"^(.+)_(\d+)$")


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
    total_count: int
    context: dict[str, Any]


def _project_output_dir(project_id: int) -> Path:
    path = Path(GENERATED_DIR) / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_template_name(name: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("_", name.strip())
    return cleaned or "template"


def _resolve_template_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _is_multiple_base(base_key: str) -> bool:
    from app.services.variable_registry import VARIABLE_REGISTRY

    defn = VARIABLE_REGISTRY.get(base_key)
    return bool(defn and defn.get("is_multiple"))


def _build_render_context(variables: list[Variable]) -> dict[str, Any]:
    """组装 docxtpl 渲染上下文，含 multiple 列表与 alias_map。"""
    context: dict[str, Any] = {}
    multiple_groups: dict[str, list[tuple[int, str]]] = {}

    for var in variables:
        value = (var.value or "").strip()
        context[var.key] = value

        match = _BASE_KEY_PATTERN.match(var.key)
        if match:
            base_key, index = match.group(1), int(match.group(2))
            if var.is_multiple or _is_multiple_base(base_key):
                multiple_groups.setdefault(base_key, []).append((index, value))
        elif var.is_multiple:
            multiple_groups.setdefault(var.key, []).append((1, value))

    for base_key, items in multiple_groups.items():
        items.sort(key=lambda item: item[0])
        values = [val for _, val in items if val]
        plural_key = f"{base_key}s"
        context[plural_key] = values
        for index, val in items:
            context[f"{base_key}_{index}"] = val
        if values and not context.get(base_key):
            context[base_key] = values[0]

    for var in variables:
        if not var.merged_from_keys:
            continue
        keep_value = var.value or ""
        for alias_key in var.merged_from_keys:
            context[alias_key] = keep_value

    return context


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

        # 加载模板列表
        stmt = (
            select(Template.id)
            .join(ProjectTemplate, ProjectTemplate.template_id == Template.id)
            .where(ProjectTemplate.project_id == project_id)
            .order_by(ProjectTemplate.id)
        )
        template_ids = list(db.scalars(stmt).all())

        # 加载变量并构建渲染上下文
        variables = list(
            db.scalars(select(Variable).where(Variable.project_id == project_id)).all()
        )
        context = _build_render_context(variables)

        task.total_count = len(template_ids)
        db.commit()

        return InitResult(
            template_ids=template_ids,
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

        template_path = _resolve_template_path(template.file_path or "")
        if not template_path.is_file():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        doc = DocxTemplate(str(template_path))
        doc.render(input.context)

        output_dir = _project_output_dir(input.project_id)
        tmp_path = output_dir / f".tmp_{template.id}_{uuid.uuid4().hex}.docx"
        doc.save(str(tmp_path))

        final_name = f"{_safe_template_name(template.name)}_{uuid.uuid4().hex[:8]}.docx"
        final_path = output_dir / final_name
        tmp_path.rename(final_path)

        generated = GeneratedFile(
            project_id=input.project_id,
            template_id=template.id,
            file_path=str(final_path),
            status="completed",
        )
        db.add(generated)
        db.commit()
        db.refresh(generated)

        activity.heartbeat(generated.id)
        logger.info("模板「%s」渲染完成: %s", template.name, final_path)

        return RenderResult(
            file_path=str(final_path),
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
def finalize_generation(project_id: int, completed_count: int) -> None:
    """完成生成任务：更新状态为 completed。"""
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
        task.updated_at = now
        task.completed_at = now

        project = db.get(Project, project_id)
        if project:
            project.status = "completed"
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
