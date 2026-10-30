# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""规则集与 active 模板绑定兼容性评估。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select

from app.models.document_template import DocumentTemplate
from app.models.rule import Rule
from app.models.rule_set import RuleSet, RuleSetItem
from app.schemas.rule_set import (
    RuleSetTemplateCompatibilityOut,
    RuleSetTemplateCompatibilityRuleOut,
)
from app.services.base import TenantScopedService


@dataclass(frozen=True, slots=True)
class _Anchor:
    concept: str
    required: bool


@dataclass(frozen=True, slots=True)
class _Evidence:
    key: str
    concept: str
    required: bool


@dataclass(frozen=True, slots=True)
class _EnabledRule:
    rule: Rule
    anchor: _Anchor
    evidence: list[_Evidence]


class RuleSetCompatibilityService(TenantScopedService[RuleSet]):
    """只读评估规则集 required anchor 可由哪些 active 模板稳定支撑。"""

    model = RuleSet

    async def analyze(self, rule_set_id: int) -> list[RuleSetTemplateCompatibilityOut]:
        pack = await self.get(rule_set_id)
        enabled_rules = await self._load_enabled_rules(pack.id)
        templates = await self._load_active_templates()
        templates.sort(key=lambda item: (item.id != pack.template_id, item.id))

        if not templates:
            return [self._no_template_report(pack.id, enabled_rules)]

        return [
            self._report_for_template(pack.id, template, enabled_rules) for template in templates
        ]

    async def _load_enabled_rules(self, rule_set_id: int) -> list[_EnabledRule]:
        rows = (
            await self.session.execute(
                select(RuleSetItem, Rule)
                .join(Rule, Rule.id == RuleSetItem.rule_id)
                .where(
                    RuleSetItem.rule_set_id == rule_set_id,
                    RuleSetItem.enabled.is_(True),
                    Rule.enabled.is_(True),
                    Rule.is_deleted.is_(False),
                    or_(Rule.tenant_id == "", Rule.tenant_id == self.tenant_id),
                )
                .order_by(RuleSetItem.execution_order.asc(), RuleSetItem.id.asc())
            )
        ).all()
        return [
            _EnabledRule(
                rule=rule,
                anchor=_extract_anchor(rule.definition),
                evidence=_extract_evidence(rule.definition),
            )
            for item, rule in rows
        ]

    async def _load_active_templates(self) -> list[DocumentTemplate]:
        rows = (
            (
                await self.session.execute(
                    select(DocumentTemplate)
                    .where(
                        DocumentTemplate.status == "active",
                        or_(
                            DocumentTemplate.tenant_id == "",
                            DocumentTemplate.tenant_id == self.tenant_id,
                        ),
                    )
                    .order_by(DocumentTemplate.id.asc())
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    def _report_for_template(
        self,
        rule_set_id: int,
        template: DocumentTemplate,
        enabled_rules: list[_EnabledRule],
    ) -> RuleSetTemplateCompatibilityOut:
        bindings = {
            str(row.get("concept_code", "")): row
            for row in template.concept_bindings or []
            if isinstance(row, dict)
        }
        rule_reports: list[RuleSetTemplateCompatibilityRuleOut] = []
        for enabled in enabled_rules:
            quality, concept, message = _combined_quality(enabled, bindings)
            rule_reports.append(
                RuleSetTemplateCompatibilityRuleOut(
                    rule_id=enabled.rule.id,
                    rule_code=enabled.rule.rule_code,
                    rule_name=enabled.rule.name,
                    concept_code=concept,
                    required=quality != "not_required",
                    action=_action_for_quality(quality),
                    binding_quality=quality,
                    message=message,
                )
            )

        exact_count = sum(row.binding_quality == "exact" for row in rule_reports)
        weak_count = sum(row.binding_quality == "weak" for row in rule_reports)
        missing_count = sum(row.binding_quality == "missing" for row in rule_reports)
        return RuleSetTemplateCompatibilityOut(
            rule_set_id=rule_set_id,
            template_id=template.id,
            template_name=template.name,
            status=_report_status(missing_count, weak_count),
            exact_count=exact_count,
            weak_count=weak_count,
            missing_count=missing_count,
            rules=rule_reports,
        )

    def _no_template_report(
        self,
        rule_set_id: int,
        enabled_rules: list[_EnabledRule],
    ) -> RuleSetTemplateCompatibilityOut:
        rules = []
        for item in enabled_rules:
            quality, concept, _ = _combined_quality(item, {})
            rules.append(
                RuleSetTemplateCompatibilityRuleOut(
                    rule_id=item.rule.id,
                    rule_code=item.rule.rule_code,
                    rule_name=item.rule.name,
                    concept_code=concept,
                    required=quality != "not_required",
                    action=_action_for_quality(quality),
                    binding_quality=quality,
                    message="当前租户没有 active 模板，规则审查将缺少模板绑定。",
                )
            )
        return RuleSetTemplateCompatibilityOut(
            rule_set_id=rule_set_id,
            template_id=None,
            template_name=None,
            status="no_template",
            missing_count=sum(row.binding_quality == "missing" for row in rules),
            rules=rules,
        )


def _extract_anchor(definition: dict[str, Any]) -> _Anchor:
    anchor = definition.get("anchor") if isinstance(definition, dict) else {}
    if not isinstance(anchor, dict):
        anchor = {}
    return _Anchor(
        concept=str(anchor.get("concept") or ""),
        required=bool(anchor.get("required", True)),
    )


def _extract_evidence(definition: dict[str, Any]) -> list[_Evidence]:
    evidence = definition.get("evidence") if isinstance(definition, dict) else {}
    if not isinstance(evidence, dict):
        return []
    return [
        _Evidence(
            key=str(key),
            concept=str(spec.get("concept") or ""),
            required=bool(spec.get("required", True)),
        )
        for key, spec in evidence.items()
        if isinstance(spec, dict)
    ]


def _combined_quality(
    enabled: _EnabledRule,
    bindings: dict[str, dict[str, Any]],
) -> tuple[str, str, str]:
    """主 anchor 与 required evidence 取最差质量，避免多证据规则被误判兼容。"""
    requirements: list[tuple[str, str, bool]] = [
        ("anchor", enabled.anchor.concept, enabled.anchor.required),
        *[(f"证据 {item.key}", item.concept, item.required) for item in enabled.evidence],
    ]
    results: list[tuple[str, str, str, int]] = []
    for label, concept, required in requirements:
        if not required:
            continue
        quality, message = _binding_quality(bindings.get(concept))
        results.append((quality, concept, f"{label}：{message}", _quality_rank(quality)))
    if not results:
        return (
            "not_required",
            enabled.anchor.concept,
            "规则 anchor 与证据均非必需，不依赖模板绑定。",
        )
    results.sort(key=lambda item: item[3], reverse=True)
    worst = results[0]
    return worst[0], worst[1], "；".join(item[2] for item in results)


def _quality_rank(quality: str) -> int:
    return {"missing": 3, "weak": 2, "exact": 1, "not_required": 0}[quality]


def _binding_quality(binding: dict[str, Any] | None) -> tuple[str, str]:
    if binding is None:
        return "missing", "模板未绑定该概念，审查时规则会跳过或需要动态解析。"
    if str(binding.get("status", "")) != "bound":
        return "missing", f"模板绑定状态为 {binding.get('status', 'unknown')}，不能作为可用定位。"

    targets = binding.get("targets")
    if not isinstance(targets, list) or not targets:
        return "missing", "模板绑定没有目标位置，不能作为可用定位。"

    has_precise_locator = any(_has_stable_locator(target) for target in targets)
    if has_precise_locator:
        return "exact", "模板已提供章节、表格或字段级稳定定位。"

    has_page_hint = any(_has_page_hint(target) for target in targets)
    if has_page_hint:
        return "weak", "模板仅有页级定位，文档内容增减后位置可能漂移。"
    return "missing", "模板绑定既无稳定定位条件，也无页码提示。"


def _has_stable_locator(target: object) -> bool:
    if not isinstance(target, dict):
        return False
    locator = target.get("locator")
    if not isinstance(locator, dict):
        return False
    stable_keys = (
        "section_title_regex",
        "anchor_keywords",
        "field_aliases",
        "image_keywords",
        "after_section",
        "stop_keywords",
    )
    return any(key in locator and _non_empty(locator[key]) for key in stable_keys)


def _has_page_hint(target: object) -> bool:
    return isinstance(target, dict) and (
        target.get("page_idx") is not None or target.get("page_idx_hint") is not None
    )


def _non_empty(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return value is not None


def _action_for_quality(quality: str) -> str:
    return {
        "exact": "reused",
        "weak": "weak_binding",
        "missing": "missing_binding",
        "not_required": "not_required",
    }[quality]


def _report_status(missing_count: int, weak_count: int) -> str:
    if missing_count:
        return "missing_binding"
    if weak_count:
        return "partial"
    return "compatible"
