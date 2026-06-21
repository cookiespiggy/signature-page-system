"""Mock Provider 预设响应数据。"""

from __future__ import annotations

import json

# AI-1: 模板解析 Mock 响应
TEMPLATE_PARSE_MOCK: dict = {
    "variables": [
        {
            "key": "law_firm_name",
            "label": "律师事务所名称",
            "category": "company",
            "data_type": "company_name",
            "required": True,
            "is_multiple": False,
            "confidence": 0.98,
            "evidence_list": ["模板中直接包含 {{law_firm_name}} 占位符"],
            "risk_note": None,
        },
        {
            "key": "law_firm_director",
            "label": "律师事务所负责人",
            "category": "lawyer",
            "data_type": "text",
            "required": True,
            "is_multiple": False,
            "confidence": 0.95,
            "evidence_list": ["模板中直接包含 {{law_firm_director}} 占位符"],
            "risk_note": None,
        },
        {
            "key": "handling_lawyer",
            "label": "经办律师",
            "category": "lawyer",
            "data_type": "text",
            "required": True,
            "is_multiple": True,
            "confidence": 0.92,
            "evidence_list": ["模板中直接包含 {{handling_lawyer}} 占位符"],
            "risk_note": "变量可能对应多个律师（多值），请确认输入时填写所有经办律师姓名",
        },
    ]
}

# AI-2: 变量去重 Mock 响应
VARIABLE_DEDUP_MOCK: dict = {
    "suggestions": [
        {
            "keep_key": "law_firm_director",
            "merge_keys": ["firm_director"],
            "reason": "语义相同，均指律师事务所负责人",
            "confidence": 0.95,
            "evidence_list": [
                "两个变量的 label 均为「律师事务所负责人」或相近表述",
                "两个变量出现在同一个项目的不同模板中",
            ],
            "risk_note": "确认两个模板的负责人角色一致后再合并",
        }
    ]
}

# AI-3: 数据校验 Mock 响应
DATA_VALIDATE_MOCK: dict = {
    "issues": [
        {
            "level": "warning",
            "variable_key": "handling_lawyer_1",
            "message": "经办律师与自然人股东姓名相同，请确认是否为同一人",
            "suggestion": "若为同一人，建议合并角色",
            "confidence": 0.72,
            "evidence_list": [
                "handling_lawyer_1 的值为「张三」",
                "natural_shareholder_name 的值也为「张三」",
            ],
            "risk_note": "同名字段在不同模板中定义不同角色，需要人工确认是否为同一人",
        }
    ]
}

MOCK_RESPONSES_BY_SCENE: dict[str, dict] = {
    "template_parse": TEMPLATE_PARSE_MOCK,
    "variable_dedup": VARIABLE_DEDUP_MOCK,
    "data_validate": DATA_VALIDATE_MOCK,
}


def get_mock_json(scene: str) -> str:
    """按场景返回 Mock JSON 字符串。"""
    data = MOCK_RESPONSES_BY_SCENE.get(scene, TEMPLATE_PARSE_MOCK)
    return json.dumps(data, ensure_ascii=False)
