# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Rule schemas. The `definition` field holds the full DSL JSON (§6.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.violation import Violation

RuleType = Literal["structured", "llm", "hybrid"]
Severity = Literal["严重", "一般", "提醒"]
BlockingPolicy = Literal["block", "advise", "observation"]
OnErrorPolicy = Literal["annotate", "skip", "fail_run"]
OutputMode = Literal["violations", "extract", "both"]
ModelProfile = Literal["text", "vision", "light"]


class RuleBase(BaseModel):
    rule_code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    rule_type: RuleType = "structured"
    classify_id: int | None = None
    severity_default: Severity = "一般"
    blocking_policy: BlockingPolicy = "block"
    on_error_policy: OnErrorPolicy = "annotate"
    output_mode: OutputMode = "violations"
    model_profile: ModelProfile | None = None
    enabled: bool = True
    # DSL JSON (anchor / ops / instruction / tools / output_schema / budget / iterate)
    definition: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class RuleCreate(RuleBase):
    pass


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    classify_id: int | None = None
    severity_default: Severity | None = None
    blocking_policy: BlockingPolicy | None = None
    on_error_policy: OnErrorPolicy | None = None
    output_mode: OutputMode | None = None
    model_profile: ModelProfile | None = None
    enabled: bool | None = None
    definition: dict[str, Any] | None = None
    note: str | None = None


class RuleOut(RuleBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: datetime


class RuleEnableResponse(BaseModel):
    id: int
    enabled: bool


class RuleTrialProfileSummary(BaseModel):
    """试跑画像摘要；避免把完整画像结构直接暴露给规则编辑表单。"""

    discovery_method: str
    template_id: int | None = None


class RuleTrialResponse(BaseModel):
    """规则样例试跑响应；结果仅用于调试，不代表正式审查记录。"""

    trial: bool = True
    status: str
    violations: list[Violation]
    extracted: dict[str, Any] | None = None
    skip_reason: str | None = None
    error: str | None = None
    duration_ms: int = 0
    binding_status: str | None = None
    profile_summary: RuleTrialProfileSummary
