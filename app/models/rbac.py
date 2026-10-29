# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""RBAC 角色、用户角色与角色菜单模型。"""

from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, IdMixin


class Role(Base, IdMixin, AuditMixin):
    """租户内角色；内置角色由代码推导权限，自定义角色保存菜单绑定。"""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_code", "code", name="uq_roles_tenant_code_code"),)

    tenant_code: Mapped[str] = mapped_column(ForeignKey("tenants.code"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_system: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")


class UserRole(Base):
    """用户与角色绑定；删除用户或角色时级联清理。"""

    __tablename__ = "user_roles"

    user_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )


class RoleMenu(Base):
    """自定义角色与菜单权限绑定。"""

    __tablename__ = "role_menus"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    menu_code: Mapped[str] = mapped_column(String(64), primary_key=True)
