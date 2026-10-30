# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Review run + per-rule execution records."""

from __future__ import annotations

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    Base,
    IdMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
)

REVIEW_STATUS = (
    "pending",
    "parsing",
    "profiling",
    "planning",
    "executing",
    "aggregating",
    "completed",
    "failed",
)
REVIEW_RESULTS = ("pass", "fail", "no_service", "failed")
RULE_EXEC_STATUS = ("success", "fallback_annotated", "skipped", "failed")


class ReviewRun(Base, IdMixin, TenantMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "review_runs"

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending", index=True
    )
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("structure_profiles.id"), nullable=True, index=True
    )
    # rule_plan: list of {rule_id, rule_name, rule_type, definition, binding_status, skip_reason}
    rule_plan: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    # violations: final aggregated violations (see Violation contract in schemas)
    violations: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    annotated_pdf_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    token_cost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class RuleExecution(Base, IdMixin, TimestampMixin):
    __tablename__ = "rule_executions"

    run_id: Mapped[int] = mapped_column(
        ForeignKey("review_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    rule_name: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="success")
    skip_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    violations: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    extracted: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    llm_io: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
