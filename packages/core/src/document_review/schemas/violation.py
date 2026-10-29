# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Violation contract (§6.2) - the single canonical output schema.

All rule execution paths (structured / llm / hybrid) produce violations in this shape.
Frontend, DB, and PDF annotation all consume from this contract.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["严重", "一般", "提醒"]


class ViolationMeta(BaseModel):
    """Per-violation metadata flags. Drives blocking decision and presentation."""

    model_config = ConfigDict(extra="allow")

    blocking: bool = True
    confidence: float | None = None
    skip_result: bool = False  # ambiguous binding => marked but doesn't fail
    observation: bool = False  # observation-only (never blocks)
    item_no: str | None = None  # if this violation ties to a specific list item
    extra: dict[str, Any] = Field(default_factory=dict)


class Violation(BaseModel):
    """Single violation item - the engine output contract."""

    rule_id: str  # rule_code like "HZ-1011-001"
    rule_name: str
    classify_id: int
    title: str
    severity: Severity
    content: str
    page_idx: int = 0  # 0-based per spec
    mark_text: list[str] = Field(default_factory=list)
    meta: ViolationMeta = Field(default_factory=ViolationMeta)
