# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Document template: detect conditions + concept bindings (one per tenant)."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, IdMixin, TenantMixin

TEMPLATE_STATUS = ("draft", "active", "retired")


class DocumentTemplate(Base, IdMixin, TenantMixin, AuditMixin):
    __tablename__ = "document_templates"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # detect_conditions: list of {type: section_title_regex | table_field_contains | md_contains, ...}
    detect_conditions: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    # concept_bindings: list of {concept_code, status, targets: [{kind, locator, page_idx_hint, confidence, confirmed_by}]}
    concept_bindings: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    source_run_id: Mapped[int | None] = mapped_column(ForeignKey("review_runs.id"), nullable=True)
    source_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("structure_profiles.id"), nullable=True
    )
