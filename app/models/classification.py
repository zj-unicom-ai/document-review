# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Classification: 1- and 2-level classification skeleton, tenant-customizable."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TenantMixin, TimestampMixin


class Classification(Base, IdMixin, TenantMixin, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "classifications"

    classify_id: Mapped[int] = mapped_column(nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("classifications.id"), nullable=True, index=True
    )
    level: Mapped[int] = mapped_column(nullable=False, default=2)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sort_order: Mapped[int] = mapped_column(nullable=False, default=0)
