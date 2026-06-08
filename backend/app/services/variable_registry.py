"""预置变量注册表、校验规则与模板变量映射。"""

from __future__ import annotations

from typing import Any, TypedDict


class VariableDefinition(TypedDict, total=False):
    label: str
    category: str
    aliases: list[str]
    required: bool
    is_multiple: bool


VARIABLE_REGISTRY: dict[str, VariableDefinition] = {
    # --- 通用变量（跨模板共享）---
    "target_company_name": {
        "label": "目标公司名称",
        "category": "company",
        "aliases": ["目标公司名称", "发行人名称", "公司名称", "股份有限公司"],
        "required": True,
    },
    "signing_date": {
        "label": "签署日期",
        "category": "date",
        "aliases": ["签署日期", "日期", "年月日"],
        "required": True,
    },
    # --- 模板1: 律所签字页专用变量 ---
    "law_firm_name": {
        "label": "律师事务所名称",
        "category": "lawyer",
        "aliases": ["律师事务所名称", "律所名称"],
        "required": True,
    },
    "law_firm_director": {
        "label": "律师事务所负责人",
        "category": "lawyer",
        "aliases": ["律师事务所负责人", "律所负责人", "负责人"],
        "required": True,
    },
    "handling_lawyer": {
        "label": "经办律师",
        "category": "lawyer",
        "aliases": ["经办律师", "签字律师"],
        "required": True,
        "is_multiple": True,
    },
    "exchange_name": {
        "label": "交易所名称",
        "category": "company",
        "aliases": ["交易所名称", "交易所", "上市交易所"],
        "required": False,
    },
    "document_type": {
        "label": "文件类型",
        "category": "document",
        "aliases": ["文件类型", "文书类型", "意见书类型"],
        "required": False,
    },
    "target_investor_type": {
        "label": "投资者类型",
        "category": "document",
        "aliases": ["投资者类型", "发行对象", "合格投资者"],
        "required": False,
    },
    # --- 模板2: 自然人股东签字页专用变量 ---
    "natural_shareholder_name": {
        "label": "自然人股东姓名",
        "category": "shareholder",
        "aliases": ["自然人股东", "股东姓名", "自然人股东姓名"],
        "required": True,
    },
    "natural_shareholder_id_number": {
        "label": "自然人股东身份证号",
        "category": "shareholder",
        "aliases": ["身份证号", "自然人股东身份证号", "身份证号码"],
        "required": False,
    },
    "meeting_year": {
        "label": "股东大会年份",
        "category": "meeting",
        "aliases": ["会议年份", "股东大会年份", "年份"],
        "required": True,
    },
    "meeting_session": {
        "label": "股东大会次数",
        "category": "meeting",
        "aliases": ["会议次数", "股东大会次数", "第几次"],
        "required": True,
    },
    # --- 模板3: 机构股东签字页专用变量 ---
    "institutional_shareholder_name": {
        "label": "机构股东名称",
        "category": "shareholder",
        "aliases": ["机构股东名称", "机构名称", "法人股东名称"],
        "required": True,
    },
    "authorized_representative_name": {
        "label": "授权代表姓名",
        "category": "shareholder",
        "aliases": ["授权代表", "执行事务合伙人委派代表", "授权代表姓名"],
        "required": True,
    },
}

VALIDATION_RULES: dict[str, str] = {
    "natural_shareholder_id_number": r"^\d{17}[\dXx]$",
    "target_company_name": r".+股份有限公司|.+有限责任公司",
    "institutional_shareholder_name": r".+",
    "signing_date": r"^\d{4}年\d{1,2}月\d{1,2}日$",
}

TEMPLATE_VARIABLE_MAP: dict[str, list[str]] = {
    "law_firm_signing_page": [
        "target_company_name",
        "law_firm_name",
        "law_firm_director",
        "handling_lawyer",
        "signing_date",
        "exchange_name",
        "document_type",
        "target_investor_type",
    ],
    "natural_shareholder_signing_page": [
        "natural_shareholder_name",
        "natural_shareholder_id_number",
        "target_company_name",
        "meeting_year",
        "meeting_session",
        "signing_date",
    ],
    "institutional_shareholder_signing_page": [
        "institutional_shareholder_name",
        "authorized_representative_name",
        "target_company_name",
        "meeting_year",
        "meeting_session",
        "signing_date",
    ],
}

_runtime_registry: dict[str, VariableDefinition] = {}


def get_merged_registry() -> dict[str, VariableDefinition]:
    """返回预置注册表与运行时自定义变量的合并结果。"""
    merged: dict[str, VariableDefinition] = dict(VARIABLE_REGISTRY)
    merged.update(_runtime_registry)
    return merged


def register_runtime_variable(key: str, definition: VariableDefinition) -> None:
    """将用户确认的自定义变量写入运行时注册表。"""
    _runtime_registry[key] = definition


def load_runtime_registry_from_db(entries: list[dict[str, Any]]) -> None:
    """从数据库 CustomVariable 记录加载运行时注册表。"""
    _runtime_registry.clear()
    for entry in entries:
        key = entry["key"]
        _runtime_registry[key] = {
            "label": entry["label"],
            "category": entry.get("category", "other"),
            "aliases": entry.get("aliases") or [],
            "required": entry.get("required", False),
            "is_multiple": entry.get("is_multiple", False),
        }
