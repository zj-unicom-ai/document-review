# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Platform user account for login and role checks."""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, IdMixin, SoftDeleteMixin


class User(Base, IdMixin, SoftDeleteMixin, AuditMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    tenant_code: Mapped[str] = mapped_column(ForeignKey("tenants.code"), nullable=False, index=True)
    # 空字符串表示 migration 创建了账号但尚未设置可用密码。
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
