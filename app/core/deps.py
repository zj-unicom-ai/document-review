# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Reusable FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db_session
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.rbac import is_valid_menu_code
from app.core.security import read_session_token
from app.core.tenant import normalize_tenant_id
from app.models.tenant import Tenant
from app.models.user import User
from app.services.rbac import RbacService

DBSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_tenant_id(
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> str:
    """Resolve tenant from header. Empty string means platform-level."""
    return normalize_tenant_id(x_tenant_id)


CurrentTenant = Annotated[str, Depends(get_tenant_id)]


async def get_current_user(request: Request, session: DBSession) -> User:
    """从 HttpOnly Cookie 恢复登录用户，权限每次从数据库实时解析。"""
    token = request.cookies.get("document_review_session")
    payload = read_session_token(token) if token else None
    if payload is None:
        raise UnauthorizedError("登录状态无效或已过期")

    user = await session.get(User, int(payload["sub"]))
    if user is None or user.is_deleted or user.status != "active":
        raise UnauthorizedError("登录状态无效或已过期")
    if user.username != payload.get("username"):
        raise UnauthorizedError("登录状态无效或已过期")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_current_super_admin(current_user: CurrentUser, session: DBSession) -> User:
    """限制平台级租户与用户管理操作。"""
    if not await RbacService(session).is_super_admin(current_user):
        raise ForbiddenError("只有平台超级管理员可以执行此操作")
    return current_user


SuperAdmin = Annotated[User, Depends(require_current_super_admin)]


async def get_authorized_tenant(
    current_user: CurrentUser,
    session: DBSession,
    x_tenant_id: Annotated[str | None, Header(alias="X-Tenant-Id")] = None,
) -> str:
    """校验请求租户与登录用户所属租户，超管可切换到已存在租户。"""
    tenant_id = normalize_tenant_id(x_tenant_id)
    rbac = RbacService(session)
    if await rbac.is_super_admin(current_user):
        if tenant_id == "":
            return ""
        tenant = (
            await session.execute(
                select(Tenant).where(Tenant.code == tenant_id, Tenant.is_deleted.is_(False))
            )
        ).scalar_one_or_none()
        if tenant is None:
            raise ForbiddenError("租户不存在或不可访问")
    else:
        tenant = (
            await session.execute(
                select(Tenant).where(
                    Tenant.code == current_user.tenant_code,
                    Tenant.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if tenant_id != current_user.tenant_code:
            raise ForbiddenError("不能访问其他租户的数据")
    if tenant is None or tenant.status != "active":
        raise ForbiddenError("租户不存在或已停用")
    return tenant_id


AuthorizedTenant = Annotated[str, Depends(get_authorized_tenant)]


def require_menu(menu_code: str) -> Callable[..., object]:
    """生成菜单权限依赖；同时强制请求租户与登录身份一致。"""
    if not is_valid_menu_code(menu_code):
        raise ValueError(f"unknown menu code: {menu_code}")

    async def dependency(
        _tenant_id: AuthorizedTenant,
        current_user: CurrentUser,
        session: DBSession,
    ) -> None:
        menus = await RbacService(session).menu_codes(current_user)
        if menu_code not in menus:
            raise ForbiddenError("当前角色没有访问该功能的权限")

    return dependency
