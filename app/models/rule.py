# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Rule: tenant-customizable review rule (definition inlined, no version table)."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    AuditMixin,
    Base,
    IdMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
)

RULE_TYPES = ("structured", "llm", "hybrid")
SEVERITY_VALUES = ("严重", "一般", "提醒")
BLOCKING_POLICY = ("block", "advise", "observation")
ON_ERROR_POLICY = ("annotate", "skip", "fail_run")
OUTPUT_MODE = ("violations", "extract", "both")
MODEL_PROFILES = ("text", "vision", "light")


class Rule(Base, IdMixin, TenantMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "rules"

    rule_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    rule_type: Mapped[str] = mapped_column(String(16), nullable=False, default="structured")
    classify_id: Mapped[int | None] = mapped_column(
        ForeignKey("classifications.id"), nullable=True, index=True
    )
    severity_default: Mapped[str] = mapped_column(String(8), nullable=False, default="一般")
    blocking_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="block")
    on_error_policy: Mapped[str] = mapped_column(String(16), nullable=False, default="annotate")
    output_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="violations")
    model_profile: Mapped[str | None] = mapped_column(String(16), nullable=True)
    enabled: Mapped[bool] = mapped_column(
        nullable=False, default=True, server_default=text("1"), index=True
    )
    # Full DSL JSON: anchor / ops / instruction / tools / output_schema / budget / iterate
    definition: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class RuleChangeLog(Base, IdMixin, TimestampMixin):
    """Lightweight audit log: who/when/diff. Not part of execution path."""

    __tablename__ = "rule_change_logs"

    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    changed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    diff: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
