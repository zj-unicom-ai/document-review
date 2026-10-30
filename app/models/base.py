# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""SQLAlchemy declarative base with shared columns."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """All tables inherit from this. Default `id` is a BIGINT surrogate key.

    Tenant-scoped tables have `tenant_id` (empty string = platform-level).
    Soft-delete via `is_deleted`. Audit fields track who/when created/updated.
    """


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditMixin(TimestampMixin):
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class TenantMixin:
    """Adds `tenant_id` (VARCHAR(64), empty string = platform-level)."""

    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="", server_default="", index=True
    )


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0"), index=True
    )


class IdMixin:
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
