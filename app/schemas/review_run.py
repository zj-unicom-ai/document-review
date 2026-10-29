# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Review run / rule execution read schemas (writes are via /reviews multipart)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.violation import Violation

ReviewStatus = Literal[
    "pending",
    "parsing",
    "profiling",
    "planning",
    "executing",
    "aggregating",
    "completed",
    "failed",
]
ReviewResult = Literal["pass", "fail", "needs_review", "no_service", "failed"]


class ReviewRunBase(BaseModel):
    file_name: str
    file_sha256: str
    file_path: str
    file_size: int = 0


class ReviewRunCreate(BaseModel):
    """Used internally after multipart upload copies the file to storage."""

    file_name: str
    file_sha256: str
    file_path: str
    file_size: int


class ReviewRunOut(ReviewRunBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    status: ReviewStatus
    profile_id: int | None
    rule_plan: list[dict[str, Any]] | None
    result: ReviewResult | None
    summary: str | None
    annotated_pdf_path: str | None
    error: str | None
    token_cost: int
    duration_ms: int
    created_at: datetime
    updated_at: datetime


class ReviewRunDetail(ReviewRunOut):
    violations: list[Violation] = Field(default_factory=list)

    @field_validator("violations", mode="before")
    @classmethod
    def normalize_null_violations(cls, value):
        """数据库 pending run 的 NULL 在 API 边界归一为空列表。"""
        return [] if value is None else value


class ReviewRunListItem(ReviewRunOut):
    """历史审查列表项；规则集名由计划快照前缀解析后关联。"""

    rule_set_name: str | None = None


class RuleExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: int
    rule_id: int
    rule_name: str
    rule_code: str
    rule_type: str
    status: str
    skip_reason: str | None
    violations: list[dict[str, Any]] | None
    extracted: dict[str, Any] | None
    tool_calls: list[dict[str, Any]] | None
    error: str | None
    duration_ms: int
    created_at: datetime
