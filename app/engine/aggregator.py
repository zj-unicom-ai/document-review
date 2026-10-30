# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""违规汇总与确定性 result 判定。"""

from __future__ import annotations

import copy
from collections import Counter
from typing import Any

from app.engine.state import AggregateResult, RuleResult


def aggregate(
    results: list[RuleResult],
    *,
    extra_violations: list[dict[str, Any]] | None = None,
) -> AggregateResult:
    """去重违规并计算 run 结果；本函数不做任何 I/O。"""
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for result in results:
        for violation in result.violations:
            meta = violation.get("meta", {})
            key = (
                violation.get("page_idx", 0),
                meta.get("item_no"),
                violation.get("title", ""),
                violation.get("content", ""),
            )
            if key not in merged:
                copied = copy.deepcopy(violation)
                copied.setdefault("meta", {}).setdefault("extra", {})
                copied["meta"]["extra"]["dedup_sources"] = [violation.get("rule_id")]
                merged[key] = copied
            else:
                sources = merged[key]["meta"]["extra"]["dedup_sources"]
                if violation.get("rule_id") not in sources:
                    sources.append(violation.get("rule_id"))

    violations = list(merged.values())
    for violation in extra_violations or []:
        meta = violation.get("meta", {})
        key = (
            violation.get("page_idx", 0),
            meta.get("item_no"),
            violation.get("title", ""),
            violation.get("content", ""),
        )
        if key not in merged:
            copied = copy.deepcopy(violation)
            merged[key] = copied
            violations.append(copied)
    has_blocking = any(_is_blocking(violation) for violation in violations)
    incomplete = not results or any(result.status != "success" for result in results)
    incomplete = incomplete or any(
        violation.get("meta", {}).get("extra", {}).get("detection_error")
        for violation in violations
    )
    status_counts = Counter(result.status for result in results)
    severity_counts = Counter(violation.get("severity", "一般") for violation in violations)
    classify_counts = Counter(str(violation.get("classify_id", 0)) for violation in violations)
    return AggregateResult(
        violations=violations,
        result="fail" if has_blocking else ("needs_review" if incomplete else "pass"),
        summary={
            "violation_count": len(violations),
            "status_counts": dict(status_counts),
            "severity_counts": dict(severity_counts),
            "classify_counts": dict(classify_counts),
        },
    )


def _is_blocking(violation: dict[str, Any]) -> bool:
    meta = violation.get("meta", {})
    return (
        bool(meta.get("blocking"))
        and not meta.get("skip_result")
        and not meta.get("observation")
        and not meta.get("extra", {}).get("detection_error")
    )
