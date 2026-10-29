# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Structure profile cache: tenant+file structure discovery result."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TenantMixin, TimestampMixin

DISCOVERY_METHOD = ("template_match", "llm_discovery")


class StructureProfile(Base, IdMixin, TenantMixin, TimestampMixin):
    __tablename__ = "structure_profiles"

    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Cached profile JSON (matches StructureProfile contract in spec)
    profile: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # Snapshot of active templates at profile time (for invalidation logic)
    template_set_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    discovery_method: Mapped[str] = mapped_column(String(24), nullable=False)
    llm_trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_templates.id"), nullable=True
    )
    source_run_id: Mapped[int | None] = mapped_column(ForeignKey("review_runs.id"), nullable=True)
