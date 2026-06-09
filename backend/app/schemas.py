"""Pydantic 请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    status: str | None = Field(None, pattern=r"^(draft|generating|completed)$")


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class BatchErrorItem(BaseModel):
    row: int | None = None
    key: str | None = None
    message: str


class BatchSummary(BaseModel):
    total: int
    succeeded: int
    failed: int


class BatchOperationResponse(BaseModel):
    """批量操作统一响应格式。"""

    success: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[BatchErrorItem] = Field(default_factory=list)
    summary: BatchSummary


class ErrorDetail(BaseModel):
    """单项操作错误响应。"""

    detail: str
    code: str | None = None
    current_updated_at: datetime | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    llm_provider: str
    llm_available: bool


# --- AI 场景结构化 Schema ---


class ParsedVariable(BaseModel):
    key: str
    label: str
    category: str = "other"
    data_type: str = "text"
    required: bool = False
    is_multiple: bool = False
    is_registered: bool = False
    trust_level: str | None = None
    suggested_key: str | None = None
    warnings: list[str] | None = None


class TemplateParseResult(BaseModel):
    variables: list[ParsedVariable]


class DedupSuggestion(BaseModel):
    keep_key: str
    merge_keys: list[str]
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class VariableDedupResult(BaseModel):
    suggestions: list[DedupSuggestion]


class ValidationIssue(BaseModel):
    level: str = Field(pattern=r"^(error|warning)$")
    variable_key: str
    message: str
    suggestion: str | None = None


class DataValidateResult(BaseModel):
    issues: list[ValidationIssue]


# --- 模板 API ---


class TemplateVariableDefinition(BaseModel):
    key: str
    label: str
    category: str = "other"
    data_type: str = "text"
    required: bool = False
    is_multiple: bool = False


class TemplateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    category: str = Field(default="other", max_length=64)
    tags: list[str] = Field(default_factory=list)
    applicable_scenarios: str | None = None
    variables_json: list[TemplateVariableDefinition] = Field(default_factory=list)
    register_custom_variables: bool = True


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(None, max_length=64)
    tags: list[str] | None = None
    applicable_scenarios: str | None = None
    variables_json: list[TemplateVariableDefinition] | None = None
    register_custom_variables: bool = True


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    category: str
    tags: list[str] | None
    applicable_scenarios: str | None
    variable_count: int
    is_preset: bool
    file_path: str | None
    variables_json: list[dict[str, Any]] | None
    version: int
    preview_image: str | None
    created_at: datetime
    updated_at: datetime


class TemplateParseResponse(BaseModel):
    variables: list[ParsedVariable]
    ai_used: bool
    parse_duration_ms: int
    message: str | None = None


class ProjectTemplateSelect(BaseModel):
    template_ids: list[int] = Field(..., min_length=1)


class ProjectTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    template_id: int
    template_version: int
    variables_snapshot_json: list[dict[str, Any]] | None
    needs_refresh: bool = False
    latest_template_version: int | None = None


class TemplateRefreshResponse(BaseModel):
    added: int
    removed: int
    kept: int


# --- 变量 API ---


class VariableResponse(BaseModel):
    key: str
    label: str
    value: str = ""
    category: str
    data_type: str
    required: bool
    is_multiple: bool
    sort_order: int
    source_template_ids: list[int] = Field(default_factory=list)
    is_merged: bool = False
    merged_from_keys: list[str] | None = None
    updated_at: datetime


class VariableListResponse(BaseModel):
    variables: list[VariableResponse]


class VariableSaveItem(BaseModel):
    key: str
    value: str = ""
    updated_at: datetime | None = None


class VariableSaveRequest(BaseModel):
    variables: list[VariableSaveItem]


class DedupSuggestionResponse(BaseModel):
    keep_key: str
    merge_keys: list[str]
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str | None = None
    trust_level: str | None = None
    rules_match: bool | None = None
    warnings: list[str] | None = None


class AiDedupResponse(BaseModel):
    alias_suggestions: list[DedupSuggestionResponse] = Field(default_factory=list)
    ai_suggestions: list[DedupSuggestionResponse] = Field(default_factory=list)
    ai_used: bool
    message: str | None = None


class ApplyDedupRequest(BaseModel):
    suggestions: list[DedupSuggestionResponse]


class ApplyDedupResponse(BaseModel):
    merged_rows: int


class ValidationIssueResponse(BaseModel):
    level: str
    variable_key: str
    message: str
    suggestion: str | None = None
    source: str | None = None
    cross_validated: bool | None = None


class AiValidateResponse(BaseModel):
    regex_issues: list[ValidationIssueResponse] = Field(default_factory=list)
    ai_issues: list[ValidationIssueResponse] = Field(default_factory=list)
    issues: list[ValidationIssueResponse] = Field(default_factory=list)
    ai_used: bool
    message: str | None = None


class ImportConfirmRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(
        ...,
        description="import-preview 返回的 success 行列表",
    )
