# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""RuleSet + RuleSetItem schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RuleSetBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    template_id: int | None = None
    is_standard_pack: bool = False
    description: str | None = None


class RuleSetCreate(RuleSetBase):
    items: list[RuleSetItemIn] = []


class RuleSetUpdate(BaseModel):
    name: str | None = None
    template_id: int | None = None
    description: str | None = None


class RuleSetItemIn(BaseModel):
    rule_id: int
    execution_order: int = 0
    enabled: bool = True
    params_override: dict[str, Any] = Field(default_factory=dict)


class RuleSetItemOut(RuleSetItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    rule_set_id: int
    created_at: datetime
    updated_at: datetime


class RuleSetOut(RuleSetBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    items: list[RuleSetItemOut] = []
    created_at: datetime
    updated_at: datetime


class RuleSetItemsBulkUpdate(BaseModel):
    items: list[RuleSetItemIn]


# BL-075：规则 anchor 与模板绑定的兼容性评估结果。
class RuleSetTemplateCompatibilityRuleOut(BaseModel):
    rule_id: int
    rule_code: str
    rule_name: str
    concept_code: str
    required: bool
    action: Literal["reused", "weak_binding", "missing_binding", "not_required"]
    binding_quality: Literal["exact", "weak", "missing", "not_required"]
    message: str


class RuleSetTemplateCompatibilityOut(BaseModel):
    rule_set_id: int
    template_id: int | None = None
    template_name: str | None = None
    status: Literal["compatible", "partial", "missing_binding", "no_template"]
    exact_count: int = 0
    weak_count: int = 0
    missing_count: int = 0
    rules: list[RuleSetTemplateCompatibilityRuleOut] = []


# Resolve forward reference
RuleSetCreate.model_rebuild()
