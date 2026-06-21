"""文档异步生成与下载业务逻辑。"""

from __future__ import annotations

import logging
import os
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.exceptions import (
    ActiveTaskExistsError,
    InvalidStateTransition,
    NoActiveTaskError,
    NoTemplatesSelectedError,
    TemplateFileMissingError,
)
from app.models import GeneratedFile, GenerationTask, Project, Template, Variable
from app.services.project_service import GENERATED_DIR, get_project
from app.services.render_utils import (
    add_audit_log,
    build_render_context,
    get_latest_task,
    get_project_templates,
    project_output_dir,
    render_one_template,
    resolve_template_path,
    safe_template_name,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)
_cancel_events: dict[int, threading.Event] = {}

ACTIVE_STATUSES = {"pending", "processing"}


class GenerationStateMachine:
    """显式状态机 — 管理 GenerationTask 和关联 Project 的状态转换。

    合法转换:
        pending    → processing | cancelled
        processing → completed | failed | cancelled
        completed  → (terminal)
        failed     → (terminal)
        cancelled  → (terminal)
    """

    TRANSITIONS: dict[str, set[str]] = {
        "pending": {"processing", "cancelled"},
        "processing": {"completed", "failed", "cancelled"},
        "completed": set(),
        "failed": set(),
        "cancelled": set(),
    }

    def __init__(
        self, task: GenerationTask, project: Project | None, db: Session
    ) -> None:
        self._task = task
        self._project = project
        self._db = db

    @property
    def status(self) -> str:
        return self._task.status

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.TRANSITIONS.get(self._task.status, set())

    def transition_to(self, new_status: str) -> None:
        """转换状态，同步更新 Project.status。"""
        if not self.can_transition_to(new_status):
            raise InvalidStateTransition(
                f"非法状态转换: {self._task.status} → {new_status}"
            )
        now = datetime.now(UTC).replace(tzinfo=None)
        self._task.status = new_status
        self._task.updated_at = now

        # 同步 Project.status
        if self._project:
            if new_status == "processing":
                self._project.status = "generating"
            elif new_status == "completed":
                self._project.status = "completed"
            elif new_status in {"failed", "cancelled"}:
                self._project.status = "draft"

        # 设置时间戳
        if new_status == "completed":
            self._task.completed_at = now
        elif new_status == "cancelled":
            self._task.cancelled_at = now

        self._db.commit()

    def update_progress(self, completed_count: int) -> None:
        """更新进度计数（不改变状态）。"""
        self._task.completed_count = completed_count
        self._db.commit()

    def mark_failed(self, error_message: str, completed_count: int) -> None:
        """标记为失败（从 processing 状态）。"""
        if not self.can_transition_to("failed"):
            return
        self._task.status = "failed"
        self._task.error_message = error_message
        self._task.completed_count = completed_count
        now = datetime.now(UTC).replace(tzinfo=None)
        self._task.updated_at = now
        if self._project and self._project.status == "generating":
            self._project.status = "draft"
        self._db.commit()


def shutdown_executor() -> None:
    """应用关闭时清理线程池。"""
    _executor.shutdown(wait=False)


def _mark_task_cancelled(
    sm: GenerationStateMachine, project_id: int, completed_count: int
) -> None:
    """通过状态机取消任务，并记录审计日志。"""
    sm._task.completed_count = completed_count
    sm.transition_to("cancelled")
    add_audit_log(
        sm._db, project_id=project_id, action="cancelled",
        message=f"生成任务已取消，已完成 {completed_count}/{sm._task.total_count} 个文件",
        generation_task_id=sm._task.id,
        details={"completed_count": completed_count, "total_count": sm._task.total_count},
    )


def _run_generation(task_id: int, project_id: int, cancel_event: threading.Event) -> None:
    db = SessionLocal()
    completed_count = 0
    try:
        task = db.get(GenerationTask, task_id)
        if task is None:
            return

        project = db.get(Project, project_id)
        sm = GenerationStateMachine(task, project, db)
        sm.transition_to("processing")

        templates = get_project_templates(db, project_id)
        variables = list(
            db.scalars(select(Variable).where(Variable.project_id == project_id)).all()
        )
        context = build_render_context(variables)
        output_dir = project_output_dir(project_id)

        for index, template in enumerate(templates):
            if cancel_event.is_set() or _is_task_cancelled_in_db(db, task_id):
                _mark_task_cancelled(sm, project_id, completed_count)
                return

            add_audit_log(
                db, project_id=project_id, action="template_started",
                message=f"模板「{template.name}」开始生成（模板版本 v{template.version}）",
                generation_task_id=task_id,
                details={"template_id": template.id, "template_name": template.name, "template_version": template.version},
            )

            generated = _render_one_template_with_cancel(
                db,
                task_id=task_id,
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
                _mark_task_cancelled(sm, project_id, completed_count)
                return

            if generated is None:
                _mark_task_cancelled(sm, project_id, completed_count)
                return

            completed_count = index + 1
            sm.update_progress(completed_count)

            filename = generated.file_path.split("/")[-1] if "/" in generated.file_path else generated.file_path
            add_audit_log(
                db, project_id=project_id, action="template_completed",
                message=f"模板「{template.name}」生成完成（模板版本 v{template.version}） → {filename}",
                generation_task_id=task_id,
                details={
                    "template_id": template.id, "template_name": template.name,
                    "template_version": template.version, "file_id": generated.id,
                    "filename": filename,
                },
            )

        sm._task.completed_count = completed_count
        sm.transition_to("completed")
        add_audit_log(
            db, project_id=project_id, action="completed",
            message=f"全部 {completed_count}/{completed_count} 个文件生成完成",
            generation_task_id=task_id,
            details={"completed_count": completed_count},
        )
    except Exception as exc:
        logger.exception("生成任务 %s 失败", task_id)
        db.rollback()
        task = db.get(GenerationTask, task_id)
        project = db.get(Project, project_id)
        if task and task.status not in {"cancelled", "completed"}:
            sm = GenerationStateMachine(task, project, db)
            sm.mark_failed(str(exc), completed_count)
            add_audit_log(
                db, project_id=project_id, action="failed",
                message=f"生成失败: {exc}",
                generation_task_id=task_id,
                details={"error": str(exc), "completed_count": completed_count},
            )
    finally:
        _cancel_events.pop(task_id, None)
        db.close()


def _render_one_template_with_cancel(
    db: Session,
    *,
    task_id: int | None,
    project_id: int,
    template: Template,
    cancel_event: threading.Event,
    context: dict[str, Any],
    output_dir: Path,
) -> GeneratedFile | None:
    """渲染单个模板（带取消信号检查）。"""
    from app.services.render_utils import render_one_template as _render

    if cancel_event.is_set():
        return None
    template_path = resolve_template_path(template.file_path or "")
    if not template_path.is_file():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")
    if cancel_event.is_set():
        return None

    generated = _render(
        db, project_id=project_id, template=template, context=context, output_dir=output_dir,
        generation_task_id=task_id,
    )
    if cancel_event.is_set() and generated:
        db.delete(generated)
        Path(generated.file_path).unlink(missing_ok=True)
        db.commit()
        return None
    return generated


def _is_task_cancelled_in_db(db: Session, task_id: int) -> bool:
    task = db.get(GenerationTask, task_id)
    return task is not None and task.status == "cancelled"


def start_generation(db: Session, project_id: int) -> GenerationTask:
    """创建生成任务并提交到线程池。"""
    get_project(db, project_id)
    templates = get_project_templates(db, project_id)
    if not templates:
        raise NoTemplatesSelectedError(
            "请先为项目选择至少一个模板"
        )

    for template in templates:
        path = resolve_template_path(template.file_path or "")
        if not path.is_file():
            raise TemplateFileMissingError(
                f"模板「{template.name}」文件缺失，无法生成"
            )

    active_stmt = select(GenerationTask).where(
        GenerationTask.project_id == project_id,
        GenerationTask.status.in_(ACTIVE_STATUSES),
    )
    if db.scalar(active_stmt):
        raise ActiveTaskExistsError("该项目已有进行中的生成任务")

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
    add_audit_log(
        db, project_id=project_id, action="started",
        message=f"生成任务已创建，共 {len(templates)} 个模板待处理",
        generation_task_id=task.id,
        details={"template_count": len(templates), "templates": [{"id": t.id, "name": t.name, "version": t.version} for t in templates]},
    )
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
        raise NoActiveTaskError("没有进行中的生成任务")

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
    add_audit_log(
        db, project_id=project_id, action="cancelled",
        message=f"生成任务已取消，已完成 {task.completed_count}/{task.total_count} 个文件",
        generation_task_id=task.id,
        details={"completed_count": task.completed_count, "total_count": task.total_count},
    )
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


def cancel_temporal_workflow_sync(task: GenerationTask) -> None:
    """同步取消 Temporal Workflow（供项目删除等同步路径调用）。"""
    if not task.workflow_id:
        return

    import asyncio

    async def _cancel():
        from app.temporal.client import get_client
        from app.temporal.workflows.generation import DocumentGenerationWorkflow

        try:
            client = await get_client()
            handle = client.get_workflow_handle_for(
                DocumentGenerationWorkflow, task.workflow_id
            )
            await handle.signal(DocumentGenerationWorkflow.cancel)
        except Exception:
            logger.exception("取消 Temporal Workflow %s 失败", task.workflow_id)

    try:
        asyncio.run(_cancel())
    except RuntimeError:
        # 如果已有事件循环（如 FastAPI 异步上下文），用 run_coroutine_threadsafe
        logger.warning("无法在同步上下文中取消 Temporal Workflow %s", task.workflow_id)


def get_generation_status(db: Session, project_id: int) -> GenerationTask | None:
    get_project(db, project_id)
    return get_latest_task(db, project_id)


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
    db: Session,
    task: GenerationTask,
    templates: list[Template],
    task_files: dict[int, GeneratedFile],
    progress: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """构建生成日志时间线 — 优先从审计日志表读取，回退到传统逻辑。"""
    from app.models import GenerationAuditLog

    audit_logs = list(
        db.scalars(
            select(GenerationAuditLog)
            .where(GenerationAuditLog.generation_task_id == task.id)
            .order_by(GenerationAuditLog.created_at.asc())
        ).all()
    )
    if audit_logs:
        _LEVEL_MAP = {
            "started": "info",
            "template_started": "info",
            "template_completed": "success",
            "completed": "success",
            "failed": "error",
            "cancelled": "warning",
        }
        return [
            {
                "timestamp": log.created_at,
                "level": _LEVEL_MAP.get(log.action, "info"),
                "message": log.message,
                "template_name": (log.details or {}).get("template_name"),
            }
            for log in audit_logs
        ]

    # 回退：无审计日志时使用传统逻辑（兼容旧数据）
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
        filename = file_record.file_path.split("/")[-1] if "/" in file_record.file_path else file_record.file_path
        logs.append(
            {
                "timestamp": file_record.created_at,
                "level": "success",
                "message": f"模板「{template.name}」生成完成 → {filename}",
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
    templates = get_project_templates(db, task.project_id)
    task_files = _task_files_by_template(db, task)
    progress = _build_template_progress(templates, task, task_files)
    logs = _build_generation_logs(db, task, templates, task_files, progress)
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
        .options(joinedload(GeneratedFile.template), joinedload(GeneratedFile.generation_task))
        .where(
            GeneratedFile.project_id == project_id,
            GeneratedFile.status == "completed",
        )
        .order_by(GeneratedFile.created_at.desc())
    )
    return list(db.scalars(stmt).unique().all())


def get_file_batches(db: Session, project_id: int) -> dict[str, Any]:
    """返回按批次分组的文件列表。"""
    from app.models import GenerationTask
    from app.schemas import GeneratedFileResponse, GenerationBatchSummary

    project = get_project(db, project_id)

    # 所有生成任务（从新到旧）
    tasks = list(
        db.scalars(
            select(GenerationTask)
            .where(GenerationTask.project_id == project_id)
            .order_by(GenerationTask.created_at.desc())
        ).all()
    )

    # 所有已完成文件，按 generation_task_id 索引
    all_files = list_generated_files(db, project_id)
    by_task: dict[int | None, list[GeneratedFile]] = {}
    for f in all_files:
        by_task.setdefault(f.generation_task_id, []).append(f)

    # 最新批次
    current_task = tasks[0] if tasks else None
    current_files = by_task.get(current_task.id, []) if current_task else []

    # 历史批次摘要
    history: list[dict] = []
    for task in tasks[1:]:
        task_files = by_task.get(task.id, [])
        history.append(GenerationBatchSummary(
            generation_task_id=task.id,
            created_at=task.created_at,
            status=task.status,
            file_count=len(task_files),
            completed_count=task.completed_count,
            total_count=task.total_count,
        ))

    def _to_response(f: GeneratedFile) -> GeneratedFileResponse:
        return GeneratedFileResponse(
            id=f.id,
            project_id=f.project_id,
            template_id=f.template_id,
            template_name=f.template.name if f.template else None,
            template_category=f.template.category if f.template else None,
            file_path=f.file_path,
            status=f.status,
            generation_task_id=f.generation_task_id,
            created_at=f.created_at,
        )

    return {
        "current": [_to_response(f) for f in current_files],
        "history": history,
        "all_files": [_to_response(f) for f in all_files],
    }


def get_generated_file(db: Session, file_id: int) -> GeneratedFile:
    stmt = (
        select(GeneratedFile)
        .options(joinedload(GeneratedFile.template))
        .where(GeneratedFile.id == file_id)
    )
    generated = db.scalar(stmt)
    if generated is None:
        raise NoActiveTaskError(f"文件 {file_id} 不存在")
    return generated


def resolve_download_path(generated: GeneratedFile) -> Path:
    path = Path(generated.file_path)
    if not path.is_file():
        raise NoActiveTaskError("文件已被删除或不存在")
    return path


def build_download_all_zip(db: Session, project_id: int) -> tuple[bytes, str]:
    """打包项目全部已生成文件，返回 (zip_bytes, filename)。"""
    project = get_project(db, project_id)
    files = list_generated_files(db, project_id)
    if not files:
        raise NoActiveTaskError("暂无可下载的生成文件")

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
