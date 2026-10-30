# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""RBAC 角色解析与租户内用户 / 角色维护服务。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.rbac import (
    ALL_MENU_CODES,
    MEMBER_ROLE,
    MENU_PERMISSIONS,
    PLATFORM_ONLY_MENUS,
    SUPER_ADMIN_ROLE,
    TENANT_ADMIN_ROLE,
    is_valid_menu_code,
)
from app.core.security import hash_password
from app.models.rbac import Role, RoleMenu, UserRole
from app.models.user import User

RESERVED_SUPERADMIN_TENANT_CODE = "superadmin"
MEMBER_ROLE_MENU = "reviews"
BUILTIN_ROLE_CODES = {SUPER_ADMIN_ROLE, TENANT_ADMIN_ROLE, MEMBER_ROLE}


class RbacService:
    """读取角色 / 权限，并维护租户内用户与角色资源。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def role_codes(self, user: User) -> list[str]:
        rows = (
            (
                await self.session.execute(
                    select(Role.code)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(
                        UserRole.user_id == user.id,
                        Role.tenant_code == user.tenant_code,
                        Role.status == "active",
                    )
                    .order_by(Role.code)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def is_super_admin(self, user: User) -> bool:
        if user.tenant_code != RESERVED_SUPERADMIN_TENANT_CODE:
            return False
        return SUPER_ADMIN_ROLE in await self.role_codes(user)

    async def menu_codes(self, user: User) -> list[str]:
        roles = await self.role_codes(user)
        allowed: set[str]
        if await self.is_super_admin(user):
            allowed = set(ALL_MENU_CODES)
        elif TENANT_ADMIN_ROLE in roles:
            allowed = set(ALL_MENU_CODES) - PLATFORM_ONLY_MENUS
        else:
            allowed = {MEMBER_ROLE_MENU} if MEMBER_ROLE in roles else set()
            if roles:
                rows = (
                    (
                        await self.session.execute(
                            select(RoleMenu.menu_code)
                            .join(Role, Role.id == RoleMenu.role_id)
                            .join(UserRole, UserRole.role_id == Role.id)
                            .where(
                                UserRole.user_id == user.id,
                                Role.tenant_code == user.tenant_code,
                                Role.status == "active",
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                allowed.update(rows)
        return [item.code for item in MENU_PERMISSIONS if item.code in allowed]

    async def ensure_builtin_roles(self, tenant_code: str, *, created_by: str = "system") -> None:
        """为租户创建内置角色；保留超管租户只创建平台超管角色。"""
        definitions = (
            [
                (SUPER_ADMIN_ROLE, "平台超级管理员", "平台内置角色，拥有全部菜单权限。"),
            ]
            if tenant_code == RESERVED_SUPERADMIN_TENANT_CODE
            else [
                (TENANT_ADMIN_ROLE, "租户管理员", "租户内置角色，拥有本租户全部可用菜单。"),
                (MEMBER_ROLE, "普通用户", "租户内置角色，默认只能使用文档审查。"),
            ]
        )
        for code, name, description in definitions:
            exists = await self.session.execute(
                select(Role.id).where(Role.tenant_code == tenant_code, Role.code == code)
            )
            if exists.scalar_one_or_none() is None:
                self.session.add(
                    Role(
                        tenant_code=tenant_code,
                        code=code,
                        name=name,
                        description=description,
                        is_system=True,
                        status="active",
                        created_by=created_by,
                        updated_by=created_by,
                    )
                )

    # ---- 用户管理 ----

    async def list_users(
        self, tenant_code: str, *, page: int = 1, page_size: int = 20, q: str | None = None
    ) -> tuple[Sequence[User], dict[int, list[Role]], int]:
        stmt = select(User).where(User.tenant_code == tenant_code, User.is_deleted.is_(False))
        count_stmt = (
            select(func.count())
            .select_from(User)
            .where(User.tenant_code == tenant_code, User.is_deleted.is_(False))
        )
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where((User.username.like(pattern)) | (User.display_name.like(pattern)))
            count_stmt = count_stmt.where(
                (User.username.like(pattern)) | (User.display_name.like(pattern))
            )
        stmt = stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        users = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        assert total >= len(users)
        user_ids = [user.id for user in users]
        roles_by_user: dict[int, list[Role]] = {user_id: [] for user_id in user_ids}
        if user_ids:
            rows = (
                await self.session.execute(
                    select(UserRole.user_id, Role)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(UserRole.user_id.in_(user_ids))
                    .order_by(Role.id)
                )
            ).all()
            for user_id, role in rows:
                roles_by_user[user_id].append(role)
        return users, roles_by_user, int(total)

    async def get_user(self, tenant_code: str, user_id: int) -> User:
        user = (
            await self.session.execute(
                select(User).where(
                    User.id == user_id,
                    User.tenant_code == tenant_code,
                    User.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if user is None:
            raise NotFoundError(f"user id={user_id} not found")
        return user

    async def user_roles(self, user: User) -> list[Role]:
        rows = (
            (
                await self.session.execute(
                    select(Role)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == user.id)
                    .order_by(Role.id)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def _active_roles(self, tenant_code: str, role_ids: list[int]) -> list[Role]:
        if not role_ids:
            raise ValidationError("用户至少需要绑定一个角色")
        if len(set(role_ids)) != len(role_ids):
            raise ValidationError("用户角色不能重复")
        roles = (
            (
                await self.session.execute(
                    select(Role)
                    .where(
                        Role.id.in_(role_ids),
                        Role.tenant_code == tenant_code,
                        Role.status == "active",
                    )
                    .order_by(Role.id)
                    # 锁住被绑定角色，串行化角色删除与用户角色替换。
                    .with_for_update(of=Role)
                )
            )
            .scalars()
            .all()
        )
        if len(roles) != len(set(role_ids)):
            raise ValidationError("包含不存在、已停用或跨租户的角色")
        return list(roles)

    async def _active_admin_count(self, tenant_code: str) -> tuple[int, str]:
        role_code = (
            SUPER_ADMIN_ROLE
            if tenant_code == RESERVED_SUPERADMIN_TENANT_CODE
            else TENANT_ADMIN_ROLE
        )
        # 锁定全部活跃管理员用户行，避免并发修改同时通过“最后一个管理员”检查。
        admin_ids = (
            (
                await self.session.execute(
                    select(User.id)
                    .join(UserRole, UserRole.user_id == User.id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(
                        User.tenant_code == tenant_code,
                        User.is_deleted.is_(False),
                        User.status == "active",
                        Role.code == role_code,
                        Role.status == "active",
                    )
                    .order_by(User.id)
                    .with_for_update(of=User)
                )
            )
            .scalars()
            .all()
        )
        return len(admin_ids), role_code

    async def _ensure_not_last_admin(
        self, user: User, *, next_status: str, next_role_ids: list[int] | None
    ) -> None:
        count, role_code = await self._active_admin_count(user.tenant_code)
        current_codes = {role.code for role in await self.user_roles(user)}
        if role_code not in current_codes or count > 1:
            return
        roles: list[Role] | None = None
        if next_role_ids is not None:
            roles = await self._active_roles(user.tenant_code, next_role_ids)
        keeps_admin = roles is None or any(role.code == role_code for role in roles)
        if next_status != "active" or not keeps_admin:
            raise ConflictError("不能删除、停用或降级最后一个管理员")

    async def create_user(
        self,
        tenant_code: str,
        data: dict,
        *,
        actor: str,
    ) -> tuple[User, list[Role]]:
        username = str(data["username"]).strip()
        existing = (
            await self.session.execute(select(User.id).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"username={username} already exists")
        roles = await self._active_roles(tenant_code, data["role_ids"])
        user = User(
            tenant_code=tenant_code,
            username=username,
            password_hash=hash_password(data["password"]),
            display_name=data.get("display_name"),
            status="active",
            created_by=actor,
            updated_by=actor,
        )
        self.session.add(user)
        await self.session.flush()
        for role in roles:
            self.session.add(UserRole(user_id=user.id, role_id=role.id))
        await self.session.commit()
        await self.session.refresh(user)
        return user, roles

    async def update_user(
        self,
        tenant_code: str,
        user_id: int,
        data: dict,
        *,
        actor: str,
    ) -> tuple[User, list[Role]]:
        user = await self.get_user(tenant_code, user_id)
        next_role_ids = data.get("role_ids")
        next_status = data.get("status", user.status)
        await self._ensure_not_last_admin(
            user, next_status=next_status, next_role_ids=next_role_ids
        )

        roles: list[Role]
        if next_role_ids is not None:
            roles = await self._active_roles(tenant_code, next_role_ids)
            await self.session.execute(delete(UserRole).where(UserRole.user_id == user.id))
            for role in roles:
                self.session.add(UserRole(user_id=user.id, role_id=role.id))
        else:
            roles = await self.user_roles(user)

        if "display_name" in data:
            user.display_name = data["display_name"]
        if "status" in data and data["status"] is not None:
            user.status = data["status"]
        if data.get("password"):
            user.password_hash = hash_password(data["password"])
        user.updated_by = actor
        await self.session.commit()
        await self.session.refresh(user)
        return user, await self.user_roles(user)

    async def delete_user(self, tenant_code: str, user_id: int, *, actor: str) -> None:
        user = await self.get_user(tenant_code, user_id)
        await self._ensure_not_last_admin(user, next_status=user.status, next_role_ids=None)
        # delete_user 的保护语义是“删除后不能再登录”，因此按最后一个管理员删除处理。
        count, role_code = await self._active_admin_count(tenant_code)
        if count <= 1 and role_code in {role.code for role in await self.user_roles(user)}:
            raise ConflictError("不能删除、停用或降级最后一个管理员")
        user.is_deleted = True
        user.updated_by = actor
        await self.session.commit()

    # ---- 角色管理 ----

    async def list_roles(
        self, tenant_code: str, *, page: int = 1, page_size: int = 20, q: str | None = None
    ) -> tuple[Sequence[Role], dict[int, int], int]:
        stmt = select(Role).where(Role.tenant_code == tenant_code)
        count_stmt = select(func.count()).select_from(Role).where(Role.tenant_code == tenant_code)
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where((Role.code.like(pattern)) | (Role.name.like(pattern)))
            count_stmt = count_stmt.where((Role.code.like(pattern)) | (Role.name.like(pattern)))
        stmt = stmt.order_by(Role.id).offset((page - 1) * page_size).limit(page_size)
        roles = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        assert total >= len(roles)
        role_ids = [role.id for role in roles]
        counts: dict[int, int] = {role_id: 0 for role_id in role_ids}
        if role_ids:
            rows = (
                await self.session.execute(
                    select(UserRole.role_id, func.count())
                    .where(UserRole.role_id.in_(role_ids))
                    .group_by(UserRole.role_id)
                )
            ).all()
            counts.update({int(role_id): int(count) for role_id, count in rows})
        return roles, counts, int(total)

    async def get_role(self, tenant_code: str, role_id: int) -> Role:
        role = (
            await self.session.execute(
                select(Role).where(Role.id == role_id, Role.tenant_code == tenant_code)
            )
        ).scalar_one_or_none()
        if role is None:
            raise NotFoundError(f"role id={role_id} not found")
        return role

    async def role_menu_codes(self, role: Role) -> list[str]:
        if role.is_system:
            if role.code == SUPER_ADMIN_ROLE:
                allowed = set(ALL_MENU_CODES)
            elif role.code == TENANT_ADMIN_ROLE:
                allowed = set(ALL_MENU_CODES) - PLATFORM_ONLY_MENUS
            else:
                allowed = set(
                    (
                        await self.session.execute(
                            select(RoleMenu.menu_code).where(RoleMenu.role_id == role.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                if role.code == MEMBER_ROLE and not allowed:
                    allowed = {MEMBER_ROLE_MENU}
        else:
            allowed = set(
                (
                    await self.session.execute(
                        select(RoleMenu.menu_code).where(RoleMenu.role_id == role.id)
                    )
                )
                .scalars()
                .all()
            )
        return [item.code for item in MENU_PERMISSIONS if item.code in allowed]

    async def _validate_custom_menus(self, menu_codes: list[str]) -> None:
        if len(set(menu_codes)) != len(menu_codes):
            raise ValidationError("菜单权限不能重复")
        for code in menu_codes:
            if not is_valid_menu_code(code):
                raise ValidationError(f"未知菜单权限: {code}")
            item = next(item for item in MENU_PERMISSIONS if item.code == code)
            if not item.assignable:
                raise ValidationError(f"菜单权限不可分配给自定义角色: {code}")

    async def create_role(self, tenant_code: str, data: dict, *, actor: str) -> Role:
        code = data["code"]
        if code in BUILTIN_ROLE_CODES:
            raise ConflictError("不能使用系统内置角色编码")
        existing = (
            await self.session.execute(
                select(Role.id).where(Role.tenant_code == tenant_code, Role.code == code)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"role code={code} already exists")
        await self._validate_custom_menus(data["menu_codes"])
        role = Role(
            tenant_code=tenant_code,
            code=code,
            name=data["name"],
            description=data.get("description"),
            is_system=False,
            status="active",
            created_by=actor,
            updated_by=actor,
        )
        self.session.add(role)
        await self.session.flush()
        for menu_code in data["menu_codes"]:
            self.session.add(RoleMenu(role_id=role.id, menu_code=menu_code))
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def update_role(self, tenant_code: str, role_id: int, data: dict, *, actor: str) -> Role:
        role = (
            await self.session.execute(
                select(Role)
                .where(Role.id == role_id, Role.tenant_code == tenant_code)
                .with_for_update(of=Role)
            )
        ).scalar_one_or_none()
        if role is None:
            raise NotFoundError(f"role id={role_id} not found")

        menu_codes = data.get("menu_codes")
        if menu_codes is not None:
            await self._validate_custom_menus(menu_codes)
            if role.code == MEMBER_ROLE and not menu_codes:
                raise ValidationError("内置普通角色至少保留一个菜单权限")
        metadata_keys = {"name", "description", "status"}
        if role.is_system:
            # member 是租户默认角色，只开放菜单调整；管理员角色固定避免锁死租户。
            if role.code != MEMBER_ROLE:
                raise ConflictError("该内置角色不允许编辑")
            if any(key in data and data[key] is not None for key in metadata_keys):
                raise ConflictError("内置普通角色只允许调整菜单权限")
        else:
            for field in ("name", "description", "status"):
                if field in data and data[field] is not None:
                    setattr(role, field, data[field])

        if menu_codes is not None:
            await self.session.execute(delete(RoleMenu).where(RoleMenu.role_id == role.id))
            for menu_code in menu_codes:
                self.session.add(RoleMenu(role_id=role.id, menu_code=menu_code))
        role.updated_by = actor
        await self.session.commit()
        await self.session.refresh(role)
        return role

    async def delete_role(self, tenant_code: str, role_id: int) -> None:
        role = (
            await self.session.execute(
                select(Role)
                .where(Role.id == role_id, Role.tenant_code == tenant_code)
                .with_for_update(of=Role)
            )
        ).scalar_one_or_none()
        if role is None:
            raise NotFoundError(f"role id={role_id} not found")
        if role.is_system:
            raise ConflictError("内置角色不允许删除")
        used = (
            await self.session.execute(
                select(func.count()).select_from(UserRole).where(UserRole.role_id == role.id)
            )
        ).scalar_one()
        if used:
            raise ConflictError("角色已分配用户，请先解绑用户")
        await self.session.delete(role)
        await self.session.commit()

    async def role_user_count(self, role_id: int) -> int:
        count = (
            await self.session.execute(
                select(func.count()).select_from(UserRole).where(UserRole.role_id == role_id)
            )
        ).scalar_one()
        return int(count)
