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
        },
        {
            "key": "law_firm_director",
            "label": "律师事务所负责人",
            "category": "lawyer",
            "data_type": "text",
            "required": True,
            "is_multiple": False,
        },
        {
            "key": "handling_lawyer",
            "label": "经办律师",
            "category": "lawyer",
            "data_type": "text",
            "required": True,
            "is_multiple": True,
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
