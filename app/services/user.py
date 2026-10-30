# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""用户认证与平台超管初始化。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.rbac import SUPER_ADMIN_ROLE
from app.core.security import hash_password, verify_password
from app.models.rbac import Role, UserRole
from app.models.tenant import Tenant
from app.models.user import User

RESERVED_SUPERADMIN_TENANT_CODE = "superadmin"
RESERVED_SUPERADMIN_USERNAME = "admin"
# 未知用户也执行一次哈希校验，减少通过响应时间探测用户名的空间。
_DUMMY_PASSWORD_HASH = hash_password("document-review-timing-equalizer")


class UserService:
    """用户读取、认证与超管初始化。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username, User.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def get(self, user_id: int) -> User:
        user = (
            await self.session.execute(
                select(User).where(User.id == user_id, User.is_deleted.is_(False))
            )
        ).scalar_one_or_none()
        if user is None:
            raise NotFoundError(f"user id={user_id} not found")
        return user

    async def authenticate(self, username: str, password: str) -> User:
        user = await self.get_by_username(username)
        # 统一返回 401，避免暴露用户名是否存在。
        password_ok = verify_password(
            password, user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
        )
        if user is None or user.status != "active" or not password_ok:
            raise UnauthorizedError("用户名或密码错误")
        return user

    async def set_superadmin_password(self, password: str) -> User:
        """为保留超管账号设置或重置密码，并确保绑定平台超管角色。"""
        tenant = (
            await self.session.execute(
                select(Tenant).where(Tenant.code == RESERVED_SUPERADMIN_TENANT_CODE)
            )
        ).scalar_one_or_none()
        if tenant is None:
            raise NotFoundError("保留租户 superadmin 不存在；请先执行数据库 migration")

        role = (
            await self.session.execute(
                select(Role).where(
                    Role.tenant_code == RESERVED_SUPERADMIN_TENANT_CODE,
                    Role.code == SUPER_ADMIN_ROLE,
                )
            )
        ).scalar_one_or_none()
        if role is None:
            role = Role(
                tenant_code=RESERVED_SUPERADMIN_TENANT_CODE,
                code=SUPER_ADMIN_ROLE,
                name="平台超级管理员",
                description="平台内置角色，拥有全部菜单权限。",
                is_system=True,
                status="active",
                created_by="bootstrap",
                updated_by="bootstrap",
            )
            self.session.add(role)
            await self.session.flush()

        user = await self.get_by_username(RESERVED_SUPERADMIN_USERNAME)
        if user is None:
            user = User(
                tenant_code=RESERVED_SUPERADMIN_TENANT_CODE,
                username=RESERVED_SUPERADMIN_USERNAME,
                display_name="平台超级管理员",
                status="active",
                created_by="bootstrap",
                updated_by="bootstrap",
            )
            self.session.add(user)
            await self.session.flush()
        if user.tenant_code != RESERVED_SUPERADMIN_TENANT_CODE:
            raise ConflictError("admin 账号已被占用，无法初始化为超管")

        binding = (
            await self.session.execute(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
            )
        ).scalar_one_or_none()
        if binding is None:
            self.session.add(UserRole(user_id=user.id, role_id=role.id))

        user.password_hash = hash_password(password)
        user.status = "active"
        user.updated_by = "bootstrap"
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def initialize_superadmin(self, password: str) -> tuple[User, bool]:
        """首次部署时初始化空密码超管；已有密码时只补齐角色绑定，不覆盖密码。"""
        user = await self.get_by_username(RESERVED_SUPERADMIN_USERNAME)
        if user is not None and user.password_hash:
            if user.tenant_code != RESERVED_SUPERADMIN_TENANT_CODE:
                raise ConflictError("admin 账号已被占用，无法初始化为超管")

            role = (
                await self.session.execute(
                    select(Role).where(
                        Role.tenant_code == RESERVED_SUPERADMIN_TENANT_CODE,
                        Role.code == SUPER_ADMIN_ROLE,
                    )
                )
            ).scalar_one_or_none()
            if role is None:
                role = Role(
                    tenant_code=RESERVED_SUPERADMIN_TENANT_CODE,
                    code=SUPER_ADMIN_ROLE,
                    name="平台超级管理员",
                    description="平台内置角色，拥有全部菜单权限。",
                    is_system=True,
                    status="active",
                    created_by="bootstrap",
                    updated_by="bootstrap",
                )
                self.session.add(role)
                await self.session.flush()

            binding = (
                await self.session.execute(
                    select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
                )
            ).scalar_one_or_none()
            if binding is None:
                self.session.add(UserRole(user_id=user.id, role_id=role.id))
                await self.session.commit()
            return user, False

        initialized_user = await self.set_superadmin_password(password)
        return initialized_user, True
