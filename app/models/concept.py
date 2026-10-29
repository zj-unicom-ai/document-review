# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Concept: platform-level semantic anchors + tenant custom concepts."""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TenantMixin, TimestampMixin

DATA_KIND_VALUES = ("document", "section", "table", "field", "image_group", "item_list")
SOURCE_VALUES = ("platform", "tenant_custom")


class Concept(Base, IdMixin, TenantMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "concepts"

    concept_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    concept_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    data_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, default="platform", server_default="platform"
    )
    seeded_from: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        # concept_code is unique per tenant
        # Using a unique constraint with tenant_id is handled in migration
    )
