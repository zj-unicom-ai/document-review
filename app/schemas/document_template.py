# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""DocumentTemplate schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.violation import Violation

TemplateStatus = Literal["draft", "active", "retired"]


class DocumentTemplateBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    status: TemplateStatus = "draft"
    description: str | None = None
    detect_conditions: list[dict[str, Any]] = Field(default_factory=list)
    concept_bindings: list[dict[str, Any]] = Field(default_factory=list)


class DocumentTemplateCreate(DocumentTemplateBase):
    pass


class DocumentTemplateUpdate(BaseModel):
    name: str | None = None
    status: TemplateStatus | None = None
    description: str | None = None
    detect_conditions: list[dict[str, Any]] | None = None
    concept_bindings: list[dict[str, Any]] | None = None


class TemplateTrialRulePreview(BaseModel):
    """模板试跑中的单条规则预览结果。"""

    rule_id: int
    rule_code: str
    rule_name: str
    rule_type: str
    status: str
    violations: list[Violation] = Field(default_factory=list)
    extracted: dict[str, Any] | None = None
    skip_reason: str | None = None
    error: str | None = None
    duration_ms: int = 0


class TemplateTrialResponse(BaseModel):
    """模板样例试跑响应；只用于画像确认与规则调试，不是正式审查。"""

    profile_id: int
    file_sha256: str
    discovery_method: str
    template_id: int | None = None
    doc_summary: str | None = None
    bindings: list[dict[str, Any]] = Field(default_factory=list)
    suggested_detect_conditions: list[dict[str, Any]] = Field(default_factory=list)
    rule_set_id: int | None = None
    rule_set_selection_reason: str
    rule_preview: list[TemplateTrialRulePreview] = Field(default_factory=list)


class DocumentTemplateFromProfileCreate(BaseModel):
    """从已确认画像固化 active 模板。"""

    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    detect_conditions: list[dict[str, Any]] = Field(min_length=1)


class DocumentTemplateOut(DocumentTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    source_run_id: int | None
    source_profile_id: int | None
    created_at: datetime
    updated_at: datetime
