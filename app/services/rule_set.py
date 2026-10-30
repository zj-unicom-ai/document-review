# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""RuleSet + RuleSetItem CRUD."""

from __future__ import annotations

from sqlalchemy import delete, select

from app.core.exceptions import ImmutableError, NotFoundError
from app.models.rule import Rule
from app.models.rule_set import RuleSet, RuleSetItem
from app.services.base import TenantScopedService


class RuleSetService(TenantScopedService[RuleSet]):
    model = RuleSet

    async def get_with_items(self, id: int) -> RuleSet:
        rs = await self.get(id)
        # items are loaded via relationship if configured; fallback to explicit query
        items = await self._load_items(id)
        rs.__dict__["items"] = list(items)  # type: ignore[attr-defined]
        return rs

    async def _load_items(self, rule_set_id: int) -> list[RuleSetItem]:

        rows = (
            (
                await self.session.execute(
                    select(RuleSetItem)
                    .where(RuleSetItem.rule_set_id == rule_set_id)
                    .order_by(RuleSetItem.execution_order.asc(), RuleSetItem.id.asc())
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def create(self, data: dict, *, created_by: str = "system") -> RuleSet:  # type: ignore[override]
        items = data.pop("items", [])
        rs = await super().create(data, created_by=created_by)
        for it in items:
            await self._validate_rule_for_tenant(it["rule_id"])
            self.session.add(
                RuleSetItem(
                    rule_set_id=rs.id,
                    rule_id=it["rule_id"],
                    execution_order=it.get("execution_order", 0),
                    enabled=it.get("enabled", True),
                    params_override=it.get("params_override", {}),
                )
            )
        await self.session.commit()
        return rs

    async def _validate_rule_for_tenant(self, rule_id: int) -> None:
        r = (
            await self.session.execute(
                Rule.__table__.select().where(Rule.id == rule_id, Rule.is_deleted.is_(False))
            )
        ).first()
        if r is None:
            raise NotFoundError(f"rule id={rule_id} not found")
        if self.tenant_id and r.tenant_id and r.tenant_id != self.tenant_id:
            raise ImmutableError("rule belongs to a different tenant")

    async def replace_items(self, rule_set_id: int, items: list[dict]) -> list[RuleSetItem]:
        await self.get(rule_set_id)
        await self.session.execute(
            delete(RuleSetItem).where(RuleSetItem.rule_set_id == rule_set_id)
        )
        for it in items:
            await self._validate_rule_for_tenant(it["rule_id"])
            self.session.add(
                RuleSetItem(
                    rule_set_id=rule_set_id,
                    rule_id=it["rule_id"],
                    execution_order=it.get("execution_order", 0),
                    enabled=it.get("enabled", True),
                    params_override=it.get("params_override", {}),
                )
            )
        await self.session.commit()
        return await self._load_items(rule_set_id)

    async def delete(self, id: int) -> None:  # type: ignore[override]
        pack = await self.get(id)
        if self.tenant_id and pack.tenant_id == "":
            raise ImmutableError("cannot delete platform-level rule sets")
        await self.session.execute(delete(RuleSetItem).where(RuleSetItem.rule_set_id == id))
        await self.session.delete(pack)
        await self.session.commit()
