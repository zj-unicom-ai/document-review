# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""External resource: Doris tables, expert library, xlsx, csv, etc."""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, IdMixin, TenantMixin

RESOURCE_TYPES = ("db_table", "file_csv", "file_xlsx", "http")


class ExternalResource(Base, IdMixin, TenantMixin, AuditMixin):
    __tablename__ = "external_resources"

    resource_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # config holds connection info / file path; secrets via env vars.
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # human-readable field list (for rule authors)
    schema_desc: Mapped[str | None] = mapped_column(String(2048), nullable=True)
