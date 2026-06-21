"""内部类型定义 — TypedDict 替代 dict[str, Any]。"""

from __future__ import annotations

from typing import Any, TypedDict


class VariableDict(TypedDict, total=False):
    """变量完整字典（从 ORM 序列化后使用）。"""

    key: str
    label: str
    value: str
    category: str
    data_type: str
    required: bool
    is_multiple: bool
    sort_order: int
    source_template_ids: list[int]
    is_merged: bool
    merged_from_keys: list[str] | None
    updated_at: Any  # datetime | str


class SaveVariableItem(TypedDict, total=False):
    """前端保存变量时的单条数据。"""

    key: str
    value: str
    updated_at: str | None


class DedupSuggestionDict(TypedDict, total=False):
    """去重建议条目。"""

    keep_key: str
    merge_keys: list[str]
    reason: str
    confidence: float
    evidence_list: list[str]
    risk_note: str
    source: str  # "alias" | "ai"


class ValidationIssueDict(TypedDict, total=False):
    """校验问题条目。"""

    level: str  # "error" | "warning"
    variable_key: str
    message: str
    suggestion: str
    confidence: float
    evidence_list: list[str]
    risk_note: str
    source: str  # "regex" | "ai"


class BatchSuccessItem(TypedDict, total=False):
    """批量操作成功条目。"""

    key: str
    value: str
    updated_at: str


class BatchErrorItem(TypedDict, total=False):
    """批量操作错误条目。"""

    row: int
    key: str | None
    message: str


class BatchSummary(TypedDict):
    """批量操作汇总。"""

    total: int
    succeeded: int
    failed: int


class BatchResult(TypedDict):
    """批量操作结果。"""

    success: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    summary: BatchSummary


class AIDedupResult(TypedDict, total=False):
    """AI 去重返回。"""

    alias_suggestions: list[DedupSuggestionDict]
    ai_suggestions: list[DedupSuggestionDict]
    ai_used: bool
    message: str | None


class AIValidateResult(TypedDict, total=False):
    """AI 校验返回。"""

    regex_issues: list[ValidationIssueDict]
    ai_issues: list[ValidationIssueDict]
    issues: list[ValidationIssueDict]
    ai_used: bool
    message: str | None


class ExcelImportRow(TypedDict, total=False):
    """Excel 导入行。"""

    row: int
    key: str | None
    value: str
    error: str


class TemplateParseResult(TypedDict, total=False):
    """模板解析返回。"""

    variables: list[dict[str, Any]]
    ai_used: bool
    parse_duration_ms: int
    message: str | None


class GenerationProgressItem(TypedDict, total=False):
    """生成进度条目。"""

    template_id: int
    template_name: str
    template_category: str
    status: str  # "pending" | "processing" | "completed" | "failed" | "skipped"
    file_id: int | None


class GenerationLogEntry(TypedDict, total=False):
    """生成日志条目。"""

    timestamp: Any
    level: str
    message: str
    template_name: str | None
