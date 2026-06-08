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
