# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Rule CRUD service (no versioning: edit in place, log diff)."""

from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import ConflictError, ImmutableError, NotFoundError
from app.models.classification import Classification
from app.models.rule import Rule, RuleChangeLog
from app.models.rule_set import RuleSet, RuleSetItem
from app.services.base import TenantScopedService
from app.services.rule_definition import validate_rule_definition


async def validate_classify_leaf(session, classify_id: int | None) -> None:
    """classify_id 必须存在，且不允许挂载在含下级明细的父级分类上。"""
    if classify_id is None:
        return
    row = (
        await session.execute(
            select(Classification).where(
                Classification.id == classify_id,
                Classification.is_deleted.is_(False),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotFoundError(f"业务分类不存在: {classify_id}")
    has_children = (
        await session.execute(
            select(Classification.id).where(
                Classification.parent_id == classify_id,
                Classification.is_deleted.is_(False),
            )
        )
    ).first()
    if has_children is not None:
        raise ConflictError("该业务分类包含下级明细，请选择最末级分类")


class RuleService(TenantScopedService[Rule]):
    model = Rule

    async def create(self, data: dict, *, created_by: str = "system") -> Rule:  # type: ignore[override]
        await validate_classify_leaf(self.session, data.get("classify_id"))
        await validate_rule_definition(
            self.session,
            self.tenant_id,
            data.get("rule_type", "structured"),
            data.get("definition") or {},
            model_profile=data.get("model_profile"),
        )
        return await super().create(data, created_by=created_by)

    async def _log_change(self, rule_id: int, before: dict, after: dict, user: str) -> None:
        diff = {
            k: {"from": before.get(k), "to": after.get(k)}
            for k in after
            if before.get(k) != after.get(k)
        }
        if not diff:
            return
        self.session.add(RuleChangeLog(rule_id=rule_id, diff=diff, changed_by=user))

    async def update(self, id: int, data: dict, *, updated_by: str = "system") -> Rule:  # type: ignore[override]
        obj = await self.get(id)
        if getattr(obj, "tenant_id", "") == "" and self.tenant_id:
            raise ImmutableError("cannot modify platform-level rules")
        if "classify_id" in data:
            await validate_classify_leaf(self.session, data.get("classify_id"))
        before = {
            k: getattr(obj, k, None)
            for k in (
                "name",
                "description",
                "definition",
                "enabled",
                "severity_default",
                "blocking_policy",
                "on_error_policy",
                "output_mode",
                "model_profile",
                "classify_id",
                "note",
            )
        }
        # profile 只更新时也要带当前 definition 校验，防止绕过算子冲突检查。
        if data.get("definition") is not None or "model_profile" in data:
            await validate_rule_definition(
                self.session,
                self.tenant_id,
                data.get("rule_type", obj.rule_type),
                data.get("definition") or obj.definition,
                model_profile=(
                    data["model_profile"]
                    if data.get("model_profile") is not None
                    else obj.model_profile
                ),
            )
        for k, v in data.items():
            if v is not None:
                setattr(obj, k, v)
        obj.updated_by = updated_by
        await self._log_change(id, before, data, updated_by)
        await self.session.commit()
        await self.session.refresh(obj)
        return obj

    async def set_enabled(self, id: int, enabled: bool, *, updated_by: str = "system") -> Rule:
        return await self.update(id, {"enabled": enabled}, updated_by=updated_by)

    async def delete(self, id: int) -> None:  # type: ignore[override]
        await self.get(id)
        referenced = await self.session.scalar(
            select(RuleSetItem.id)
            .join(RuleSet, RuleSetItem.rule_set_id == RuleSet.id)
            .where(RuleSetItem.rule_id == id)
            .limit(1)
        )
        if referenced is not None:
            raise ConflictError("规则仍被规则集引用，请先从规则集移除后再删除")
        await super().delete(id)
