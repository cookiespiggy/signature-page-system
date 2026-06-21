"""文档渲染共享工具函数 — 双模式复用（ThreadPoolExecutor + Temporal）。"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from sqlalchemy.orm import Session

from app.models import GeneratedFile, GenerationAuditLog, Template, Variable
from app.services.project_service import GENERATED_DIR
from app.services.variable_registry import VARIABLE_REGISTRY

_BASE_KEY_PATTERN = re.compile(r"^(.+)_(\d+)$")
_UNSAFE_FILENAME = re.compile(r"[^\w\-_.一-龥]+")


def safe_template_name(name: str) -> str:
    cleaned = _UNSAFE_FILENAME.sub("_", name.strip())
    return cleaned or "template"


def resolve_template_path(file_path: str) -> Path:
    path = Path(file_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def project_output_dir(project_id: int) -> Path:
    path = Path(GENERATED_DIR) / str(project_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_multiple_base(base_key: str) -> bool:
    defn = VARIABLE_REGISTRY.get(base_key)
    return bool(defn and defn.get("is_multiple"))


def build_render_context(variables: list[Variable]) -> dict[str, Any]:
    """组装 docxtpl 渲染上下文，含 multiple 列表与 alias_map。"""
    context: dict[str, Any] = {}
    multiple_groups: dict[str, list[tuple[int, str]]] = {}

    for var in variables:
        value = (var.value or "").strip()
        context[var.key] = value

        match = _BASE_KEY_PATTERN.match(var.key)
        if match:
            base_key, index = match.group(1), int(match.group(2))
            if var.is_multiple or is_multiple_base(base_key):
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


def get_project_templates(db: Session, project_id: int) -> list[Template]:
    from sqlalchemy import select
    from app.models import Template, ProjectTemplate

    stmt = (
        select(Template)
        .join(ProjectTemplate, ProjectTemplate.template_id == Template.id)
        .where(ProjectTemplate.project_id == project_id)
        .order_by(ProjectTemplate.id)
    )
    return list(db.scalars(stmt).all())


def get_latest_task(db: Session, project_id: int):
    from sqlalchemy import select
    from app.models import GenerationTask

    stmt = (
        select(GenerationTask)
        .where(GenerationTask.project_id == project_id)
        .order_by(GenerationTask.created_at.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def render_one_template(
    db: Session,
    *,
    project_id: int,
    template: Template,
    context: dict[str, Any],
    output_dir: Path,
    generation_task_id: int | None = None,
) -> GeneratedFile | None:
    """渲染单个模板并保存。返回 GeneratedFile 记录，或 None。"""
    template_path = resolve_template_path(template.file_path or "")
    if not template_path.is_file():
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    doc = DocxTemplate(str(template_path))
    doc.render(context)

    tmp_path = output_dir / f".tmp_{template.id}_{uuid.uuid4().hex}.docx"
    doc.save(str(tmp_path))

    final_name = f"{safe_template_name(template.name)}_{uuid.uuid4().hex[:8]}.docx"
    final_path = output_dir / final_name
    tmp_path.rename(final_path)

    generated = GeneratedFile(
        project_id=project_id,
        template_id=template.id,
        file_path=str(final_path),
        status="completed",
        template_version=template.version,
        generation_task_id=generation_task_id,
    )
    db.add(generated)
    db.commit()
    db.refresh(generated)
    return generated


def add_audit_log(
    db: Session,
    project_id: int,
    action: str,
    message: str,
    generation_task_id: int | None = None,
    details: dict | None = None,
) -> None:
    """添加生成审计日志记录。"""
    log = GenerationAuditLog(
        project_id=project_id,
        generation_task_id=generation_task_id,
        action=action,
        message=message,
        details=details,
    )
    db.add(log)
    db.flush()
