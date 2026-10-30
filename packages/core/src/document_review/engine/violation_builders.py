# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""规则违规装配器：structured / llm / hybrid 共用。"""

from __future__ import annotations

import re
from typing import Any

from document_review.engine.state import RulePlanItem
from document_review.schemas.violation import Violation, ViolationMeta


def build_anomaly(plan: RulePlanItem, error: str) -> dict[str, Any]:
    """单规则失败兜底违规（宁严不松口径）。"""
    violation = Violation(
        rule_id=plan.rule_code,
        rule_name=plan.rule_name,
        classify_id=plan.classify_id or 0,
        title=f"{plan.rule_name}检测异常",
        severity="一般",
        content=f"规则执行失败，需人工复核：{error[:1800]}",
        page_idx=0,
        meta=ViolationMeta(blocking=True, extra={"detection_error": True}),
    )
    return violation.model_dump(mode="json")


def build_llm_violation(
    plan: RulePlanItem,
    item: dict[str, Any],
    *,
    confidence: float | None = None,
    reasoning: str | None = None,
    fallback_page_idx: int = 0,
) -> dict[str, Any]:
    """把 LLM 输出的业务命中装配为全局 Violation 契约。"""
    severity = plan.severity_default
    observation = plan.blocking_policy == "observation"
    meta = ViolationMeta(
        blocking=severity not in ("提醒",)
        and plan.blocking_policy not in ("advise", "observation"),
        confidence=confidence,
        observation=observation,
        extra={"source": "llm", **({"reasoning": reasoning} if reasoning else {})},
    )
    violation = Violation(
        rule_id=plan.rule_code,
        rule_name=plan.rule_name,
        classify_id=plan.classify_id or 0,
        title=str(item.get("title") or plan.rule_name),
        severity=severity,
        content=_compact_content(item.get("content")),
        page_idx=int(item.get("page_idx", fallback_page_idx) or 0),
        mark_text=list(item.get("mark_text") or []),
        meta=meta,
    )
    return violation.model_dump(mode="json")


def _compact_content(value: Any) -> str:
    """压缩批注正文长度，保留一句可读结论，避免侧栏被长解释占满。"""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= 80:
        return text
    window = text[:80]
    for idx in range(len(window) - 1, -1, -1):
        if window[idx] in "。；！？":
            return window[: idx + 1]
    return window[:79].rstrip() + "…"
