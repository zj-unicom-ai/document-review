# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Base CRUD service. All tenant-scoped services inherit this."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ImmutableError, NotFoundError
from app.models.base import Base, SoftDeleteMixin, TenantMixin

M = TypeVar("M", bound=Base)


class TenantScopedService(Generic[M]):
    """CRUD for tenant-scoped resources.

    - Read: current tenant + platform (tenant_id="")
    - Write: current tenant only; platform rows are immutable from API
    """

    model: type[M]
    # set to True for models that do NOT have tenant_id (e.g. Tenant, Operator)
    is_platform_table: bool = False

    def __init__(self, session: AsyncSession, tenant_id: str = "") -> None:
        self.session = session
        self.tenant_id = tenant_id

    # ---- helpers ----
    def _has_tenant(self) -> bool:
        return any(issubclass(c, TenantMixin) for c in self.model.__mro__)

    def _has_soft_delete(self) -> bool:
        return any(issubclass(c, SoftDeleteMixin) for c in self.model.__mro__)

    def _read_filter(self):
        clauses = []
        if self._has_soft_delete():
            clauses.append(self.model.is_deleted.is_(False))  # type: ignore[attr-defined]
        if self._has_tenant() and not self.is_platform_table:
            # 平台身份（tenant_id=""）只看到平台行；租户身份看到自己 + 平台。
            # 之前漏写 else 分支，平台身份不过滤 → 跨租户泄漏（BL-002 E3 暴露）。
            if self.tenant_id:
                clauses.append(
                    or_(
                        self.model.tenant_id == self.tenant_id,  # type: ignore[attr-defined]
                        self.model.tenant_id == "",
                    )
                )
            else:
                clauses.append(self.model.tenant_id == "")  # type: ignore[attr-defined]
        elif self._has_tenant() and self.is_platform_table:
            # Tenant table itself: caller filters explicitly when needed
            pass
        return clauses

    # ---- CRUD ----
    async def list(
        self, *, page: int = 1, page_size: int = 20, q: str | None = None
    ) -> tuple[Sequence[M], int]:
        stmt = select(self.model)
        count_stmt = select(func.count()).select_from(self.model)
        for c in self._read_filter():
            stmt = stmt.where(c)
            count_stmt = count_stmt.where(c)
        # search by name/code if present
        if q:
            for col_name in (
                "name",
                "code",
                "rule_code",
                "concept_code",
                "resource_key",
                "op_code",
            ):
                if hasattr(self.model, col_name):
                    col = getattr(self.model, col_name)
                    stmt = stmt.where(col.like(f"%{q}%"))
                    count_stmt = count_stmt.where(col.like(f"%{q}%"))
                    break
        stmt = stmt.order_by(self.model.id.desc()).offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        total = (await self.session.execute(count_stmt)).scalar_one()
        return rows, int(total)

    async def get(self, id: int) -> M:
        stmt = select(self.model).where(self.model.id == id)
        for c in self._read_filter():
            stmt = stmt.where(c)
        obj = (await self.session.execute(stmt)).scalar_one_or_none()
        if obj is None:
            raise NotFoundError(f"{self.model.__name__} id={id} not found")
        return obj

    async def create(self, data: dict[str, Any], *, created_by: str = "system") -> M:
        if self._has_tenant() and not self.is_platform_table:
            data.setdefault("tenant_id", self.tenant_id)
        if hasattr(self.model, "created_by"):
            data["created_by"] = created_by
        if hasattr(self.model, "updated_by"):
            data["updated_by"] = created_by
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def update(self, id: int, data: dict[str, Any], *, updated_by: str = "system") -> M:
        obj = await self.get(id)
        # immutability check: cannot edit platform-level rows via tenant API
        if (
            self._has_tenant()
            and not self.is_platform_table
            and getattr(obj, "tenant_id", "") == ""
            and self.tenant_id
        ):
            raise ImmutableError("cannot modify platform-level rows")
        for k, v in data.items():
            setattr(obj, k, v)
        if hasattr(obj, "updated_by"):
            obj.updated_by = updated_by  # type: ignore[attr-defined]
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:
        obj = await self.get(id)
        if (
            self._has_tenant()
            and not self.is_platform_table
            and getattr(obj, "tenant_id", "") == ""
            and self.tenant_id
        ):
            raise ImmutableError("cannot delete platform-level rows")
        if self._has_soft_delete():
            obj.is_deleted = True  # type: ignore[attr-defined]
        else:
            await self.session.delete(obj)
        if hasattr(obj, "updated_by"):
            obj.updated_by = "system"  # type: ignore[attr-defined]
        await self.session.commit()
