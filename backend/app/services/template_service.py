"""模板业务逻辑 — 文件处理、CRUD、项目关联、变量同步。"""

from __future__ import annotations

import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from docx import Document
from docx.text.paragraph import Paragraph
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CustomVariable, Project, ProjectTemplate, Template, Variable
from app.services import ai_service
from app.services.ai_guardrail import cross_validate_parsed_variables
from app.services.project_service import get_project
from app.services.variable_registry import (
    TEMPLATE_VARIABLE_MAP,
    VARIABLE_REGISTRY,
    get_merged_registry,
    load_runtime_registry_from_db,
    register_runtime_variable,
)

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
PRESET_TEMPLATES_DIR = APP_DIR / "templates"
CUSTOM_TEMPLATES_DIR = Path(os.getenv("CUSTOM_TEMPLATES_DIR", "data/templates/custom"))
DEFAULT_MULTIPLE_ROWS = 2

PRESET_TEMPLATE_DEFS: list[dict[str, Any]] = [
    {
        "slug": "law_firm_signing_page",
        "name": "律所签字页",
        "description": "适用于律所出具法律意见书的签字页",
        "category": "lawyer_signing",
        "tags": ["IPO", "法律意见书", "律所"],
        "applicable_scenarios": "IPO 上市项目法律意见书",
    },
    {
        "slug": "natural_shareholder_signing_page",
        "name": "自然人股东签字页",
        "description": "适用于自然人股东签署股东大会决议的签字页",
        "category": "natural_shareholder",
        "tags": ["股东大会", "自然人股东"],
        "applicable_scenarios": "股东大会决议签字页（自然人股东）",
    },
    {
        "slug": "institutional_shareholder_signing_page",
        "name": "机构股东签字页",
        "description": "适用于机构股东（法人）签署股东大会决议的签字页",
        "category": "institutional_shareholder",
        "tags": ["股东大会", "机构股东"],
        "applicable_scenarios": "股东大会决议签字页（机构股东）",
    },
]

DATA_TYPE_BY_KEY: dict[str, str] = {
    "target_company_name": "company_name",
    "institutional_shareholder_name": "company_name",
    "natural_shareholder_id_number": "id_number",
    "signing_date": "date",
}


def extract_text_from_docx(file_path: str | Path) -> str:
    """从 .docx 文件中提取纯文本供 AI 解析。"""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"模板文件不存在: {path}")
    if path.suffix.lower() != ".docx":
        raise ValueError(f"仅支持 .docx 文件: {path.suffix}")

    try:
        doc = Document(str(path))
    except Exception as exc:
        raise ValueError(f"无法打开 .docx 文件: {exc}") from exc

    parts: list[str] = []

    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

        if tag == "p":
            para = _find_paragraph(doc, element)
            if para and para.text.strip():
                parts.append(para.text.strip())

        elif tag == "tbl":
            for row in element.iter(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr"
            ):
                cells = []
                for cell in row.iter(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tc"
                ):
                    texts = [
                        t.text or ""
                        for t in cell.iter(
                            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
                        )
                    ]
                    cells.append("".join(texts).strip())
                if cells:
                    parts.append(" | ".join(cells))

    return "\n".join(parts)


def _find_paragraph(doc: Document, element) -> Paragraph | None:
    for para in doc.paragraphs:
        if para._element is element:
            return para
    return None


def _infer_data_type(key: str) -> str:
    if key in DATA_TYPE_BY_KEY:
        return DATA_TYPE_BY_KEY[key]
    if key.endswith("_date") or "date" in key:
        return "date"
    if "id_number" in key:
        return "id_number"
    if "company" in key or "firm_name" in key:
        return "company_name"
    return "text"


def build_variable_definition(key: str, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """从注册表构建变量定义，支持 AI/用户覆盖字段。"""
    registry = get_merged_registry()
    defn = registry.get(key, {})
    item = {
        "key": key,
        "label": defn.get("label", key),
        "category": defn.get("category", "other"),
        "data_type": _infer_data_type(key),
        "required": defn.get("required", False),
        "is_multiple": defn.get("is_multiple", False),
    }
    if overrides:
        for field in ("label", "category", "data_type", "required", "is_multiple"):
            if field in overrides and overrides[field] is not None:
                item[field] = overrides[field]
    return item


def build_variables_json_from_keys(keys: list[str]) -> list[dict[str, Any]]:
    return [build_variable_definition(key) for key in keys]


def is_key_registered(key: str) -> bool:
    return key in get_merged_registry()


def enrich_parsed_variables(variables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for var in variables:
        key = var.get("key", "")
        base = build_variable_definition(key, var)
        base["is_registered"] = is_key_registered(key)
        enriched.append(base)
    return enriched


def _base_key(key: str) -> str:
    match = re.match(r"^(.+)_(\d+)$", key)
    return match.group(1) if match else key


async def save_upload_file(upload: UploadFile, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(upload.filename or "template.docx").suffix.lower()
    if suffix != ".docx":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 .docx 文件",
        )
    filename = f"{uuid.uuid4().hex[:12]}{suffix}"
    dest_path = dest_dir / filename
    content = await upload.read()
    dest_path.write_bytes(content)
    return dest_path


def load_runtime_registry(db: Session) -> None:
    stmt = select(CustomVariable)
    entries = [
        {
            "key": cv.key,
            "label": cv.label,
            "category": cv.category,
            "data_type": cv.data_type,
            "aliases": cv.aliases or [],
            "required": False,
            "is_multiple": False,
        }
        for cv in db.scalars(stmt).all()
    ]
    load_runtime_registry_from_db(entries)


def seed_preset_templates(db: Session) -> None:
    """确保 3 个预置模板存在于数据库中。"""
    PRESET_TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    for preset in PRESET_TEMPLATE_DEFS:
        slug = preset["slug"]
        file_path = PRESET_TEMPLATES_DIR / f"{slug}.docx"
        if not file_path.is_file():
            logger.warning("预置模板文件缺失: %s，跳过种子数据", file_path)
            continue

        existing = db.scalar(
            select(Template).where(
                Template.is_preset.is_(True),
                Template.name == preset["name"],
            )
        )
        keys = TEMPLATE_VARIABLE_MAP.get(slug, [])
        variables_json = build_variables_json_from_keys(keys)

        if existing:
            existing.file_path = str(file_path)
            existing.variables_json = variables_json
            existing.variable_count = len(variables_json)
            existing.description = preset["description"]
            existing.category = preset["category"]
            existing.tags = preset["tags"]
            existing.applicable_scenarios = preset["applicable_scenarios"]
        else:
            db.add(
                Template(
                    name=preset["name"],
                    description=preset["description"],
                    category=preset["category"],
                    tags=preset["tags"],
                    applicable_scenarios=preset["applicable_scenarios"],
                    variable_count=len(variables_json),
                    is_preset=True,
                    file_path=str(file_path),
                    variables_json=variables_json,
                    version=1,
                )
            )
    db.commit()


def list_templates(db: Session) -> list[Template]:
    stmt = select(Template).order_by(Template.is_preset.desc(), Template.name)
    return list(db.scalars(stmt).all())


def get_template(db: Session, template_id: int) -> Template:
    template = db.get(Template, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模板 {template_id} 不存在",
        )
    return template


def _register_custom_variables(
    db: Session,
    variables: list[dict[str, Any]],
    *,
    template_id: int | None = None,
) -> None:
    for var in variables:
        key = var["key"]
        if key in VARIABLE_REGISTRY:
            continue
        register_runtime_variable(
            key,
            {
                "label": var["label"],
                "category": var.get("category", "other"),
                "aliases": var.get("aliases") or [var["label"]],
                "required": var.get("required", False),
                "is_multiple": var.get("is_multiple", False),
            },
        )
        existing = db.scalar(select(CustomVariable).where(CustomVariable.key == key))
        if existing is None:
            db.add(
                CustomVariable(
                    key=key,
                    label=var["label"],
                    category=var.get("category", "other"),
                    data_type=var.get("data_type", "text"),
                    aliases=var.get("aliases") or [var["label"]],
                    created_by_template_id=template_id,
                )
            )


def create_template(
    db: Session,
    *,
    name: str,
    description: str | None,
    category: str,
    tags: list[str] | None,
    applicable_scenarios: str | None,
    variables_json: list[dict[str, Any]],
    file_path: str,
    register_custom: bool = True,
) -> Template:
    normalized_vars = [build_variable_definition(v["key"], v) for v in variables_json]
    template = Template(
        name=name,
        description=description,
        category=category,
        tags=tags or [],
        applicable_scenarios=applicable_scenarios,
        variable_count=len(normalized_vars),
        is_preset=False,
        file_path=file_path,
        variables_json=normalized_vars,
        version=1,
    )
    db.add(template)
    db.flush()

    if register_custom:
        custom_vars = [v for v in normalized_vars if v["key"] not in VARIABLE_REGISTRY]
        if custom_vars:
            _register_custom_variables(db, custom_vars, template_id=template.id)

    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template_id: int,
    *,
    name: str | None = None,
    description: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    applicable_scenarios: str | None = None,
    variables_json: list[dict[str, Any]] | None = None,
    file_path: str | None = None,
    register_custom: bool = True,
) -> Template:
    template = get_template(db, template_id)
    changed = False

    if name is not None:
        template.name = name
    if description is not None:
        template.description = description
    if category is not None:
        template.category = category
    if tags is not None:
        template.tags = tags
    if applicable_scenarios is not None:
        template.applicable_scenarios = applicable_scenarios

    if file_path is not None:
        old_path = template.file_path
        template.file_path = file_path
        changed = True
        if old_path and not template.is_preset and old_path != file_path:
            Path(old_path).unlink(missing_ok=True)

    if variables_json is not None:
        normalized_vars = [build_variable_definition(v["key"], v) for v in variables_json]
        template.variables_json = normalized_vars
        template.variable_count = len(normalized_vars)
        changed = True
        if register_custom:
            custom_vars = [v for v in normalized_vars if v["key"] not in VARIABLE_REGISTRY]
            if custom_vars:
                _register_custom_variables(db, custom_vars, template_id=template.id)

    if changed:
        template.version += 1

    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: int) -> None:
    template = get_template(db, template_id)
    if template.is_preset:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="预置模板不可删除",
        )

    ref_count = db.scalar(
        select(func.count()).select_from(ProjectTemplate).where(
            ProjectTemplate.template_id == template_id
        )
    )
    if ref_count and ref_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="模板仍被项目引用，请先从相关项目中移除后再删除",
        )

    if template.file_path:
        Path(template.file_path).unlink(missing_ok=True)
    db.delete(template)
    db.commit()


async def parse_template_file(upload: UploadFile) -> dict[str, Any]:
    """AI 解析上传的模板文件，返回变量列表。"""
    start = time.monotonic()
    tmp_dir = CUSTOM_TEMPLATES_DIR / "_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = await save_upload_file(upload, tmp_dir)

    try:
        text = extract_text_from_docx(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)

    ai_used = True
    try:
        result = await ai_service.parse_template_variables(text)
        variables = enrich_parsed_variables(result.get("variables", []))
        variables = cross_validate_parsed_variables(variables)
        trust_counts: dict[str, int] = {}
        for v in variables:
            tl = v.get("trust_level", "unknown")
            trust_counts[tl] = trust_counts.get(tl, 0) + 1
        logger.info(
            "AI 模板解析完成: %d 变量, 可信分布 %s",
            len(variables), trust_counts,
        )
    except ai_service.AIServiceUnavailableError:
        ai_used = False
        variables = []

    duration_ms = int((time.monotonic() - start) * 1000)
    response: dict[str, Any] = {
        "variables": variables,
        "ai_used": ai_used,
        "parse_duration_ms": duration_ms,
    }
    if not ai_used:
        response["message"] = ai_service.AI_UNAVAILABLE_MSG
    return response


def _recompute_sort_order(db: Session, project_id: int) -> None:
    stmt = (
        select(Variable)
        .where(Variable.project_id == project_id)
        .order_by(Variable.category, Variable.sort_order, Variable.key)
    )
    variables = list(db.scalars(stmt).all())
    for index, var in enumerate(variables, start=1):
        var.sort_order = index


def _compute_required_for_key(
    db: Session,
    project_id: int,
    key: str,
    source_template_ids: list[int],
) -> bool:
    if not source_template_ids:
        return False
    stmt = select(ProjectTemplate).where(
        ProjectTemplate.project_id == project_id,
        ProjectTemplate.template_id.in_(source_template_ids),
    )
    for pt in db.scalars(stmt).all():
        snapshot = pt.variables_snapshot_json or []
        for var_def in snapshot:
            if var_def.get("key") == key and var_def.get("required"):
                return True
    return False


def _find_variable_by_base_key(
    variables: list[Variable],
    base_key: str,
) -> Variable | None:
    for var in variables:
        if _base_key(var.key) == base_key:
            return var
    return None


def _find_multiple_rows(variables: list[Variable], base_key: str) -> list[Variable]:
    rows = [v for v in variables if _base_key(v.key) == base_key]
    return sorted(rows, key=lambda v: v.key)


def _add_source_template_id(var: Variable, template_id: int) -> None:
    ids = list(var.source_template_ids or [])
    if template_id not in ids:
        ids.append(template_id)
        var.source_template_ids = ids


def _sync_variables_for_new_template(
    db: Session,
    project_id: int,
    template_id: int,
    variables_snapshot: list[dict[str, Any]],
) -> None:
    """为新选模板同步 Variable 表（精确 key 去重）。"""
    existing = list(
        db.scalars(select(Variable).where(Variable.project_id == project_id)).all()
    )

    for var_def in variables_snapshot:
        base_key = var_def["key"]
        is_multiple = var_def.get("is_multiple", False)

        if is_multiple:
            rows = _find_multiple_rows(existing, base_key)
            if rows:
                for row in rows:
                    _add_source_template_id(row, template_id)
                    row.required = _compute_required_for_key(
                        db, project_id, base_key, row.source_template_ids or []
                    )
            else:
                for i in range(1, DEFAULT_MULTIPLE_ROWS + 1):
                    row_key = f"{base_key}_{i}"
                    var = Variable(
                        project_id=project_id,
                        key=row_key,
                        label=var_def.get("label", base_key),
                        value="",
                        data_type=var_def.get("data_type", "text"),
                        category=var_def.get("category", "other"),
                        is_multiple=True,
                        required=var_def.get("required", False),
                        sort_order=0,
                        source_template_ids=[template_id],
                    )
                    db.add(var)
                    existing.append(var)
        else:
            matched = _find_variable_by_base_key(existing, base_key)
            if matched:
                _add_source_template_id(matched, template_id)
                matched.required = _compute_required_for_key(
                    db, project_id, base_key, matched.source_template_ids or []
                )
            else:
                var = Variable(
                    project_id=project_id,
                    key=base_key,
                    label=var_def.get("label", base_key),
                    value="",
                    data_type=var_def.get("data_type", "text"),
                    category=var_def.get("category", "other"),
                    is_multiple=False,
                    required=var_def.get("required", False),
                    sort_order=0,
                    source_template_ids=[template_id],
                )
                db.add(var)
                existing.append(var)

    _recompute_sort_order(db, project_id)


def add_templates_to_project(
    db: Session,
    project_id: int,
    template_ids: list[int],
) -> list[ProjectTemplate]:
    get_project(db, project_id)
    added: list[ProjectTemplate] = []

    for template_id in template_ids:
        template = get_template(db, template_id)
        existing_pt = db.scalar(
            select(ProjectTemplate).where(
                ProjectTemplate.project_id == project_id,
                ProjectTemplate.template_id == template_id,
            )
        )
        if existing_pt:
            continue

        snapshot = list(template.variables_json or [])
        pt = ProjectTemplate(
            project_id=project_id,
            template_id=template_id,
            template_version=template.version,
            variables_snapshot_json=snapshot,
        )
        db.add(pt)
        db.flush()
        _sync_variables_for_new_template(db, project_id, template_id, snapshot)
        added.append(pt)

    db.commit()
    for pt in added:
        db.refresh(pt)
    return added


def list_project_templates(db: Session, project_id: int) -> list[ProjectTemplate]:
    get_project(db, project_id)
    stmt = (
        select(ProjectTemplate)
        .where(ProjectTemplate.project_id == project_id)
        .order_by(ProjectTemplate.id)
    )
    return list(db.scalars(stmt).all())


def remove_template_from_project(
    db: Session,
    project_id: int,
    template_id: int,
) -> None:
    get_project(db, project_id)
    pt = db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.project_id == project_id,
            ProjectTemplate.template_id == template_id,
        )
    )
    if pt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 未关联模板 {template_id}",
        )

    variables = list(
        db.scalars(select(Variable).where(Variable.project_id == project_id)).all()
    )
    for var in variables:
        ids = [tid for tid in (var.source_template_ids or []) if tid != template_id]
        var.source_template_ids = ids
        if not ids:
            db.delete(var)

    db.delete(pt)
    _recompute_sort_order(db, project_id)
    db.commit()


def refresh_project_template(
    db: Session,
    project_id: int,
    template_id: int,
) -> dict[str, int]:
    """刷新项目中的模板版本，diff 同步 Variable 表。"""
    get_project(db, project_id)
    template = get_template(db, template_id)
    pt = db.scalar(
        select(ProjectTemplate).where(
            ProjectTemplate.project_id == project_id,
            ProjectTemplate.template_id == template_id,
        )
    )
    if pt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"项目 {project_id} 未关联模板 {template_id}",
        )

    old_snapshot = pt.variables_snapshot_json or []
    new_snapshot = list(template.variables_json or [])
    old_keys = {v["key"] for v in old_snapshot}
    new_keys = {v["key"] for v in new_snapshot}
    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    kept_keys = old_keys & new_keys

    existing = list(
        db.scalars(select(Variable).where(Variable.project_id == project_id)).all()
    )

    for key in added_keys:
        var_def = next(v for v in new_snapshot if v["key"] == key)
        is_multiple = var_def.get("is_multiple", False)
        if is_multiple:
            for i in range(1, DEFAULT_MULTIPLE_ROWS + 1):
                row_key = f"{key}_{i}"
                var = Variable(
                    project_id=project_id,
                    key=row_key,
                    label=var_def.get("label", key),
                    value="",
                    data_type=var_def.get("data_type", "text"),
                    category=var_def.get("category", "other"),
                    is_multiple=True,
                    required=var_def.get("required", False),
                    sort_order=0,
                    source_template_ids=[template_id],
                )
                db.add(var)
        else:
            matched = _find_variable_by_base_key(existing, key)
            if matched:
                _add_source_template_id(matched, template_id)
            else:
                var = Variable(
                    project_id=project_id,
                    key=key,
                    label=var_def.get("label", key),
                    value="",
                    data_type=var_def.get("data_type", "text"),
                    category=var_def.get("category", "other"),
                    is_multiple=False,
                    required=var_def.get("required", False),
                    sort_order=0,
                    source_template_ids=[template_id],
                )
                db.add(var)

    for key in removed_keys:
        var_def = next(v for v in old_snapshot if v["key"] == key)
        if var_def.get("is_multiple"):
            rows = _find_multiple_rows(existing, key)
            for var in rows:
                ids = [tid for tid in (var.source_template_ids or []) if tid != template_id]
                var.source_template_ids = ids
                if not ids:
                    db.delete(var)
        else:
            var = _find_variable_by_base_key(existing, key)
            if var:
                ids = [tid for tid in (var.source_template_ids or []) if tid != template_id]
                var.source_template_ids = ids
                if not ids:
                    db.delete(var)

    for key in kept_keys:
        var = _find_variable_by_base_key(existing, key)
        if var:
            var.required = _compute_required_for_key(
                db, project_id, key, var.source_template_ids or []
            )

    pt.variables_snapshot_json = new_snapshot
    pt.template_version = template.version
    _recompute_sort_order(db, project_id)
    db.commit()

    return {
        "added": len(added_keys),
        "removed": len(removed_keys),
        "kept": len(kept_keys),
    }
