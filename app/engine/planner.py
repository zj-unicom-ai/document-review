# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""规则集选择与一次 run 内的规则计划快照。"""

from __future__ import annotations

import copy
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.model_routing import validate_model_routing
from app.engine.state import RulePlanItem
from app.models.concept import Concept
from app.models.rule import Rule
from app.models.rule_set import RuleSet, RuleSetItem
from app.schemas.rule import RuleCreate


class RuleSetNotSelectedError(ValueError):
    """无法唯一确定本次执行的规则集。"""


class InvalidRuleOverrideError(ValueError):
    """规则集参数覆盖试图改变 DSL 结构。"""


async def select_rule_set(
    session: AsyncSession,
    tenant_id: str,
    rule_set_id: int | None,
    profile: dict | None,
) -> RuleSet:
    """显式优先；未显式时只接受模板唯一绑定的规则集。"""
    if rule_set_id is not None:
        rule_set = (
            await session.execute(
                select(RuleSet).where(
                    RuleSet.id == rule_set_id,
                    or_(RuleSet.tenant_id == "", RuleSet.tenant_id == tenant_id),
                )
            )
        ).scalar_one_or_none()
        if rule_set is None:
            raise RuleSetNotSelectedError(f"规则集不存在或租户不可见: {rule_set_id}")
        return rule_set

    template_id = (profile or {}).get("template_id")
    if template_id is None:
        raise RuleSetNotSelectedError("未传 rule_set_id，且画像未命中模板；必须显式指定规则集")
    candidates = (
        (
            await session.execute(
                select(RuleSet).where(
                    RuleSet.template_id == template_id,
                    or_(RuleSet.tenant_id == "", RuleSet.tenant_id == tenant_id),
                )
            )
        )
        .scalars()
        .all()
    )
    if len(candidates) != 1:
        raise RuleSetNotSelectedError(
            f"模板 {template_id} 绑定了 {len(candidates)} 个规则集；必须显式指定 rule_set_id"
        )
    return candidates[0]


async def build_rule_plan(
    session: AsyncSession,
    tenant_id: str,
    rule_set: RuleSet,
    profile: dict,
) -> list[RulePlanItem]:
    """加载规则快照并完成 anchor × binding 计划。"""
    items = (
        (
            await session.execute(
                select(RuleSetItem)
                .where(RuleSetItem.rule_set_id == rule_set.id)
                .order_by(RuleSetItem.execution_order.asc(), RuleSetItem.id.asc())
            )
        )
        .scalars()
        .all()
    )
    if not items:
        return []
    rules = {
        row.id: row
        for row in (
            (
                await session.execute(
                    select(Rule).where(
                        Rule.id.in_([item.rule_id for item in items]),
                        Rule.is_deleted.is_(False),
                        or_(Rule.tenant_id == "", Rule.tenant_id == tenant_id),
                    )
                )
            )
            .scalars()
            .all()
        )
    }
    plan: list[RulePlanItem] = []
    for item in items:
        if not item.enabled:
            continue
        rule = rules.get(item.rule_id)
        if rule is None or not rule.enabled:
            continue

        plan.append(
            _build_plan_item(rule, f"{rule_set.id}:{item.id}", profile, item.params_override)
        )
    return plan


async def build_rule_plan_for_rules(
    session: AsyncSession,
    tenant_id: str,
    rule_ids: Sequence[int],
    profile: dict,
) -> list[RulePlanItem]:
    """按规则 ID 构建计划，供回归等无规则集场景复用。"""
    unique_ids = list(dict.fromkeys(rule_ids))
    if not unique_ids:
        return []
    rules = {
        row.id: row
        for row in (
            (
                await session.execute(
                    select(Rule).where(
                        Rule.id.in_(unique_ids),
                        Rule.is_deleted.is_(False),
                        Rule.enabled.is_(True),
                        or_(Rule.tenant_id == "", Rule.tenant_id == tenant_id),
                    )
                )
            )
            .scalars()
            .all()
        )
    }
    return [
        _build_plan_item(rules[rule_id], f"rules:{rule_id}", profile)
        for rule_id in unique_ids
        if rule_id in rules
    ]


async def build_rule_plan_for_draft(
    session: AsyncSession,
    tenant_id: str,
    payload: RuleCreate,
    profile: dict,
) -> RulePlanItem:
    """把未落库的规则草稿装配为单条执行计划项。"""
    concept_code = (payload.definition or {}).get("anchor", {}).get("concept", "")
    concept = (
        (
            await session.execute(
                select(Concept).where(
                    Concept.concept_code == concept_code,
                    Concept.is_deleted.is_(False),
                    Concept.tenant_id.in_(["", tenant_id]),
                )
            )
        )
        .scalars()
        .first()
    )
    if concept is None:
        raise ValueError(f"概念不存在或租户不可见: {concept_code}")

    # 草稿对象只用于复用规则计划装配逻辑，不加入 session、不写数据库。
    draft = Rule(
        id=0,
        tenant_id=tenant_id,
        rule_code=payload.rule_code,
        name=payload.name,
        description=payload.description,
        rule_type=payload.rule_type,
        classify_id=payload.classify_id,
        severity_default=payload.severity_default,
        blocking_policy=payload.blocking_policy,
        on_error_policy=payload.on_error_policy,
        output_mode=payload.output_mode,
        model_profile=payload.model_profile,
        enabled=payload.enabled,
        definition=payload.definition,
    )
    return _build_plan_item(draft, "trial:0", profile)


def _build_plan_item(
    rule: Rule,
    plan_item_id: str,
    profile: dict,
    params_override: dict | None = None,
) -> RulePlanItem:
    """把规则主表行装配为执行计划项，并完成绑定状态判定。"""
    bindings = {row.get("concept_code"): row for row in profile.get("bindings", [])}
    override = params_override or {}

    definition = copy.deepcopy(rule.definition)
    base_params = definition.get("params", {})
    unknown_keys = set(override) - set(base_params)
    if unknown_keys:
        raise InvalidRuleOverrideError(
            f"规则 {rule.rule_code} 的 params_override 含未定义 key: "
            f"{sorted(unknown_keys)}；只允许覆盖已有 params 值"
        )
    definition["params"] = {**base_params, **override}

    anchor = definition.get("anchor", {})
    concept = anchor.get("concept", "")
    required = anchor.get("required", True)
    binding = bindings.get(concept)
    binding_status = (binding or {}).get("status", "not_found")
    skip_reason: str | None = None
    if binding_status in ("not_found", "ambiguous") and required:
        skip_reason = f"概念 {concept} 未绑定或绑定不确定（{binding_status}）"
    elif binding_status in ("not_found", "ambiguous"):
        binding_status = "locator_fallback"
    evidence_skip_reason = _evidence_skip_reason(definition, bindings)
    if evidence_skip_reason is not None:
        skip_reason = (
            f"{skip_reason}；{evidence_skip_reason}" if skip_reason else evidence_skip_reason
        )
        binding_status = "not_found"

    model_profile = validate_model_routing(rule)
    return RulePlanItem(
        plan_item_id=plan_item_id,
        rule_id=rule.id,
        rule_code=rule.rule_code,
        rule_name=rule.name,
        rule_type=rule.rule_type,
        definition=definition,
        binding=binding,
        classify_id=rule.classify_id,
        severity_default=rule.severity_default,
        blocking_policy=rule.blocking_policy,
        on_error_policy=rule.on_error_policy,
        output_mode=rule.output_mode,
        binding_status=binding_status,
        skip_reason=skip_reason,
        model_profile=model_profile,
    )


def _evidence_skip_reason(definition: dict, bindings: dict) -> str | None:
    """required 多证据缺失时显式跳过，不默认通过。"""
    evidence = definition.get("evidence")
    if not isinstance(evidence, dict):
        return None
    for key, spec in evidence.items():
        if not isinstance(spec, dict) or spec.get("required", True) is False:
            continue
        concept = str(spec.get("concept", ""))
        binding = bindings.get(concept)
        status = (binding or {}).get("status", "not_found")
        targets = (binding or {}).get("targets")
        if status != "bound" or not isinstance(targets, list) or not targets:
            return f"证据 {key} 未绑定或绑定不确定（概念 {concept}，{status}）"
    return None
