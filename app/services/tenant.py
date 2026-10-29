# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Tenant CRUD service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ImmutableError, NotFoundError
from app.models.tenant import Tenant
from app.services.rbac import RbacService


class TenantService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, *, page: int = 1, page_size: int = 20, q: str | None = None
    ) -> tuple[list[Tenant], int]:
        from sqlalchemy import func

        stmt = select(Tenant).where(Tenant.is_deleted.is_(False))
        count_stmt = select(func.count()).select_from(Tenant).where(Tenant.is_deleted.is_(False))
        if q:
            stmt = stmt.where(Tenant.name.like(f"%{q}%"))
            count_stmt = count_stmt.where(Tenant.name.like(f"%{q}%"))
        stmt = stmt.order_by(Tenant.id.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        return list(rows), int(total)

    async def get(self, id: int) -> Tenant:
        obj = (
            await self.session.execute(
                select(Tenant).where(Tenant.id == id, Tenant.is_deleted.is_(False))
            )
        ).scalar_one_or_none()
        if obj is None:
            raise NotFoundError(f"tenant id={id} not found")
        return obj

    async def get_by_code(self, code: str) -> Tenant | None:
        return (
            await self.session.execute(
                select(Tenant).where(Tenant.code == code, Tenant.is_deleted.is_(False))
            )
        ).scalar_one_or_none()

    async def create(self, data: dict, *, created_by: str = "system") -> Tenant:
        existing = await self.get_by_code(data["code"])
        if existing is not None:
            raise ConflictError(f"tenant code={data['code']} already exists")
        obj = Tenant(
            code=data["code"],
            name=data["name"],
            contact=data.get("contact"),
            note=data.get("note"),
            status=data.get("status", "active"),
            created_by=created_by,
            updated_by=created_by,
        )
        self.session.add(obj)
        await self.session.flush()
        # 租户与内置角色必须同事务落库，避免出现没有管理员角色的半开通租户。
        await RbacService(self.session).ensure_builtin_roles(data["code"], created_by=created_by)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, id: int, data: dict, *, updated_by: str = "system") -> Tenant:
        obj = await self.get(id)
        if obj.code == "superadmin" and data.get("status") not in (None, "active"):
            raise ImmutableError("保留超管租户不能停用")
        for k in ("name", "status", "contact", "note"):
            if k in data and data[k] is not None:
                setattr(obj, k, data[k])
        obj.updated_by = updated_by
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:
        obj = await self.get(id)
        if obj.code == "superadmin":
            raise ImmutableError("保留超管租户不能删除")
        obj.is_deleted = True
        obj.updated_by = "system"
        await self.session.commit()
