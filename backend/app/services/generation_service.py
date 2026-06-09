"""文档异步生成与下载业务逻辑。"""

from __future__ import annotations

import logging
import os
import re
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import GeneratedFile, GenerationTask, Project, ProjectTemplate, Template, Variable
from app.services.project_service import GENERATED_DIR, get_project

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
_cancel_events: dict[int, threading.Event] = {}

ACTIVE_STATUSES = {"pending", "processing"}
_BASE_KEY_PATTERN = re.compile(r"^(.+)_(\d+)$")
_UNSAFE_FILENAME = re.compile(r"[^\w\-_.\u4e00-\u9fff]+")


def shutdown_executor() -> None:
    """应用关闭时清理线程池。"""
    _executor.shutdown(wait=False)


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


def _get_project_templates(db: Session, project_id: int) -> list[Template]:
    stmt = (
        select(Template)
        .join(ProjectTemplate, ProjectTemplate.template_id == Template.id)
        .where(ProjectTemplate.project_id == project_id)
        .order_by(ProjectTemplate.id)
    )
    return list(db.scalars(stmt).all())


def _get_latest_task(db: Session, project_id: int) -> GenerationTask | None:
    stmt = (
        select(GenerationTask)
        .where(GenerationTask.project_id == project_id)
        .order_by(GenerationTask.created_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def _render_one_template(
    db: Session,
    *,
    project_id: int,
    template: Template,
    cancel_event: threading.Event,
    context: dict[str, Any],
    output_dir: Path,
) -> GeneratedFile | None:
    """渲染单个模板，分步检查取消信号。"""
    if cancel_event.is_set():
        return None

    template_path = _resolve_template_path(template.file_path or "")
    if not template_path.is_file():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    doc = DocxTemplate(str(template_path))

    if cancel_event.is_set():
        return None

    doc.render(context)

    if cancel_event.is_set():
        return None

    tmp_path = output_dir / f".tmp_{template.id}_{uuid.uuid4().hex}.docx"
    doc.save(str(tmp_path))

    if cancel_event.is_set():
        tmp_path.unlink(missing_ok=True)
        return None

    final_name = f"{_safe_template_name(template.name)}_{uuid.uuid4().hex[:8]}.docx"
    final_path = output_dir / final_name
    tmp_path.rename(final_path)

    generated = GeneratedFile(
        project_id=project_id,
        template_id=template.id,
        file_path=str(final_path),
        status="completed",
    )
    db.add(generated)
    db.commit()
    db.refresh(generated)
    return generated


def _mark_task_cancelled(db: Session, task: GenerationTask, completed_count: int) -> None:
    now = datetime.now(UTC).replace(tzinfo=None)
    task.status = "cancelled"
    task.completed_count = completed_count
    task.cancelled_at = now
    db.commit()


def _run_generation(task_id: int, project_id: int, cancel_event: threading.Event) -> None:
    db = SessionLocal()
    completed_count = 0
    try:
        task = db.get(GenerationTask, task_id)
        if task is None:
            return

        task.status = "processing"
        db.commit()

        project = db.get(Project, project_id)
        if project:
            project.status = "generating"
            db.commit()

        templates = _get_project_templates(db, project_id)
        variables = list(
            db.scalars(select(Variable).where(Variable.project_id == project_id)).all()
        )
        context = _build_render_context(variables)
        output_dir = _project_output_dir(project_id)

        for index, template in enumerate(templates):
            if cancel_event.is_set() or _is_task_cancelled_in_db(db, task_id):
                _mark_task_cancelled(db, task, completed_count)
                return

            generated = _render_one_template(
                db,
                project_id=project_id,
                template=template,
                cancel_event=cancel_event,
                context=context,
                output_dir=output_dir,
            )

            if cancel_event.is_set() or _is_task_cancelled_in_db(db, task_id):
                db.refresh(task)
                if generated is not None:
                    completed_count = index + 1
                _mark_task_cancelled(db, task, completed_count)
                return

            if generated is None:
                _mark_task_cancelled(db, task, completed_count)
                return

            completed_count = index + 1
            task.completed_count = completed_count
            db.commit()

        now = datetime.now(UTC).replace(tzinfo=None)
        task.status = "completed"
        task.completed_count = completed_count
        task.completed_at = now
        if project:
            project.status = "completed"
        db.commit()
    except Exception as exc:
        logger.exception("生成任务 %s 失败", task_id)
        db.rollback()
        task = db.get(GenerationTask, task_id)
        if task and task.status not in {"cancelled", "completed"}:
            task.status = "failed"
            task.error_message = str(exc)
            task.completed_count = completed_count
            db.commit()
        project = db.get(Project, project_id)
        if project and project.status == "generating":
            project.status = "draft"
            db.commit()
    finally:
        _cancel_events.pop(task_id, None)
        db.close()


def _is_task_cancelled_in_db(db: Session, task_id: int) -> bool:
    task = db.get(GenerationTask, task_id)
    return task is not None and task.status == "cancelled"


def start_generation(db: Session, project_id: int) -> GenerationTask:
    """创建生成任务并提交到线程池。"""
    get_project(db, project_id)
    templates = _get_project_templates(db, project_id)
    if not templates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请先为项目选择至少一个模板",
        )

    for template in templates:
        path = _resolve_template_path(template.file_path or "")
        if not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"模板「{template.name}」文件缺失，无法生成",
            )

    active_stmt = select(GenerationTask).where(
        GenerationTask.project_id == project_id,
        GenerationTask.status.in_(ACTIVE_STATUSES),
    )
    if db.scalar(active_stmt):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该项目已有进行中的生成任务",
        )

    task = GenerationTask(
        project_id=project_id,
        status="pending",
        total_count=len(templates),
        completed_count=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    cancel_event = threading.Event()
    _cancel_events[task.id] = cancel_event
    _executor.submit(_run_generation, task.id, project_id, cancel_event)
    return task


def cancel_generation(db: Session, project_id: int) -> GenerationTask:
    """取消项目当前进行中的生成任务。"""
    get_project(db, project_id)
    stmt = select(GenerationTask).where(
        GenerationTask.project_id == project_id,
        GenerationTask.status.in_(ACTIVE_STATUSES),
    )
    task = db.scalar(stmt)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有进行中的生成任务",
        )

    now = datetime.now(UTC).replace(tzinfo=None)
    task.status = "cancelled"
    task.cancelled_at = now
    db.commit()

    event = _cancel_events.get(task.id)
    if event:
        event.set()

    project = db.get(Project, project_id)
    if project and project.status == "generating":
        project.status = "draft"
        db.commit()

    db.refresh(task)
    return task


def cancel_generation_task(task_id: int, *, set_db: bool = True) -> None:
    """供项目删除等场景调用：通知线程并可选更新 DB。"""
    event = _cancel_events.get(task_id)
    if event:
        event.set()

    if not set_db:
        return

    db = SessionLocal()
    try:
        task = db.get(GenerationTask, task_id)
        if task and task.status in ACTIVE_STATUSES:
            now = datetime.now(UTC).replace(tzinfo=None)
            task.status = "cancelled"
            task.cancelled_at = now
            db.commit()
    finally:
        db.close()


def get_generation_status(db: Session, project_id: int) -> GenerationTask | None:
    get_project(db, project_id)
    return _get_latest_task(db, project_id)


def _task_files_by_template(
    db: Session, task: GenerationTask
) -> dict[int, GeneratedFile]:
    """本次任务起创建的生成文件，按 template_id 索引。"""
    stmt = (
        select(GeneratedFile)
        .options(joinedload(GeneratedFile.template))
        .where(
            GeneratedFile.project_id == task.project_id,
            GeneratedFile.created_at >= task.created_at,
        )
        .order_by(GeneratedFile.created_at.asc())
    )
    rows = list(db.scalars(stmt).unique().all())
    by_template: dict[int, GeneratedFile] = {}
    for row in rows:
        by_template[row.template_id] = row
    return by_template


def _template_item_status(
    index: int, task: GenerationTask, completed_count: int
) -> str:
    if task.status == "completed":
        return "completed" if index < completed_count else "skipped"
    if task.status == "failed":
        if index < completed_count:
            return "completed"
        if index == completed_count:
            return "failed"
        return "pending"
    if task.status == "cancelled":
        return "completed" if index < completed_count else "skipped"
    if task.status == "processing":
        if index < completed_count:
            return "completed"
        if index == completed_count:
            return "processing"
        return "pending"
    return "pending"


def _build_template_progress(
    templates: list[Template],
    task: GenerationTask,
    task_files: dict[int, GeneratedFile],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, template in enumerate(templates):
        file_record = task_files.get(template.id)
        items.append(
            {
                "template_id": template.id,
                "template_name": template.name,
                "template_category": template.category or "other",
                "status": _template_item_status(index, task, task.completed_count),
                "file_id": file_record.id if file_record else None,
            }
        )
    return items


def _build_generation_logs(
    task: GenerationTask,
    templates: list[Template],
    task_files: dict[int, GeneratedFile],
    progress: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = [
        {
            "timestamp": task.created_at,
            "level": "info",
            "message": f"生成任务已创建，共 {task.total_count} 个模板待处理",
            "template_name": None,
        }
    ]

    if task.status in {"processing", "completed", "failed", "cancelled"}:
        logs.append(
            {
                "timestamp": task.updated_at,
                "level": "info",
                "message": "后台生成已开始",
                "template_name": None,
            }
        )

    for template in templates:
        file_record = task_files.get(template.id)
        if file_record is None:
            continue
        logs.append(
            {
                "timestamp": file_record.created_at,
                "level": "success",
                "message": f"「{template.name}」生成完成",
                "template_name": template.name,
            }
        )

    if task.status == "processing":
        current = next(
            (item for item in progress if item["status"] == "processing"),
            None,
        )
        if current:
            logs.append(
                {
                    "timestamp": task.updated_at,
                    "level": "info",
                    "message": f"正在生成「{current['template_name']}」…",
                    "template_name": current["template_name"],
                }
            )

    if task.status == "failed" and task.error_message:
        failed_item = next(
            (item for item in progress if item["status"] == "failed"),
            None,
        )
        logs.append(
            {
                "timestamp": task.updated_at,
                "level": "error",
                "message": task.error_message,
                "template_name": failed_item["template_name"] if failed_item else None,
            }
        )

    if task.status == "cancelled":
        logs.append(
            {
                "timestamp": task.cancelled_at or task.updated_at,
                "level": "warning",
                "message": (
                    f"任务已取消，已完成 {task.completed_count}/{task.total_count} 个文件"
                ),
                "template_name": None,
            }
        )

    if task.status == "completed" and task.completed_at:
        logs.append(
            {
                "timestamp": task.completed_at,
                "level": "success",
                "message": f"全部 {task.total_count} 个文件生成完成",
                "template_name": None,
            }
        )

    logs.sort(key=lambda item: item["timestamp"])
    return logs


def build_generation_status_response(db: Session, task: GenerationTask) -> dict[str, Any]:
    """组装带模板进度与日志的生成状态响应。"""
    templates = _get_project_templates(db, task.project_id)
    task_files = _task_files_by_template(db, task)
    progress = _build_template_progress(templates, task, task_files)
    logs = _build_generation_logs(task, templates, task_files, progress)
    return {
        "id": task.id,
        "project_id": task.project_id,
        "status": task.status,
        "total_count": task.total_count,
        "completed_count": task.completed_count,
        "error_message": task.error_message,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
        "cancelled_at": task.cancelled_at,
        "template_progress": progress,
        "logs": logs,
    }


def list_generated_files(db: Session, project_id: int) -> list[GeneratedFile]:
    get_project(db, project_id)
    stmt = (
        select(GeneratedFile)
        .options(joinedload(GeneratedFile.template))
        .where(
            GeneratedFile.project_id == project_id,
            GeneratedFile.status == "completed",
        )
        .order_by(GeneratedFile.created_at.desc())
    )
    return list(db.scalars(stmt).unique().all())


def get_generated_file(db: Session, file_id: int) -> GeneratedFile:
    stmt = (
        select(GeneratedFile)
        .options(joinedload(GeneratedFile.template))
        .where(GeneratedFile.id == file_id)
    )
    generated = db.scalar(stmt)
    if generated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"文件 {file_id} 不存在",
        )
    return generated


def resolve_download_path(generated: GeneratedFile) -> Path:
    path = Path(generated.file_path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件已被删除或不存在",
        )
    return path


def build_download_all_zip(db: Session, project_id: int) -> tuple[bytes, str]:
    """打包项目全部已生成文件，返回 (zip_bytes, filename)。"""
    project = get_project(db, project_id)
    files = list_generated_files(db, project_id)
    if not files:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="暂无可下载的生成文件",
        )

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    zip_name = f"project_{project_id}_all_{timestamp}.zip"
    zip_dir = Path(GENERATED_DIR) / str(project_id) / "zip"
    zip_dir.mkdir(parents=True, exist_ok=True)

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        used_names: set[str] = set()
        for gf in files:
            src = resolve_download_path(gf)
            arc_name = src.name
            if arc_name in used_names:
                arc_name = f"{gf.id}_{arc_name}"
            used_names.add(arc_name)
            zf.write(src, arcname=arc_name)

    zip_bytes = buffer.getvalue()
    disk_path = zip_dir / zip_name
    disk_path.write_bytes(zip_bytes)
    return zip_bytes, zip_name
