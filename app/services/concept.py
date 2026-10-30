# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Concept CRUD service."""

from __future__ import annotations

from sqlalchemy import or_, select

from app.core.exceptions import ConflictError, ImmutableError
from app.models.concept import Concept
from app.models.rule import Rule
from app.services.base import TenantScopedService


class ConceptService(TenantScopedService[Concept]):
    model = Concept

    async def create(self, data: dict, *, created_by: str = "system") -> Concept:  # type: ignore[override]
        # 模型的 source 默认是 "platform"，但租户建的概念应该标 tenant_custom，
        # 否则 source=="platform" 守卫会把 update/delete 拒掉。
        if self.tenant_id and not data.get("source"):
            data["source"] = "tenant_custom"
        concept_code = str(data.get("concept_code", ""))
        existing = (
            (
                await self.session.execute(
                    select(Concept).where(
                        Concept.concept_code == concept_code,
                        Concept.is_deleted.is_(False),
                        or_(Concept.tenant_id == "", Concept.tenant_id == self.tenant_id),
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            if existing.tenant_id != self.tenant_id:
                raise ConflictError(f"平台概念已存在同 concept_code: {concept_code}")
            raise ConflictError(f"concept_code={concept_code} 已存在")
        return await super().create(data, created_by=created_by)

    async def update(self, id: int, data: dict, *, updated_by: str = "system") -> Concept:  # type: ignore[override]
        obj = await self.get(id)
        # platform concepts are immutable from API
        if getattr(obj, "source", None) == "platform":
            raise ImmutableError("platform concepts are immutable")
        if getattr(obj, "tenant_id", "") == "" and self.tenant_id:
            raise ImmutableError("cannot modify platform-level concepts")
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def delete(self, id: int) -> None:  # type: ignore[override]
        obj = await self.get(id)
        if getattr(obj, "source", None) == "platform":
            raise ImmutableError("platform concepts are immutable")
        if getattr(obj, "tenant_id", "") == "" and self.tenant_id:
            raise ImmutableError("cannot delete platform-level concepts")

        rules = (
            (
                await self.session.execute(
                    select(Rule).where(
                        Rule.is_deleted.is_(False),
                        or_(Rule.tenant_id == "", Rule.tenant_id == self.tenant_id),
                    )
                )
            )
            .scalars()
            .all()
        )
        referencing = [
            row
            for row in rules
            if (row.definition or {}).get("anchor", {}).get("concept") == obj.concept_code
        ]
        if referencing:
            codes = ", ".join(row.rule_code for row in referencing[:3])
            raise ConflictError(f"概念仍被规则引用（{codes}），请先修改或删除相关规则")

        obj.is_deleted = True
        await self.session.commit()
