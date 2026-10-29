# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Review Harness：期望证据与期望违规的确定性评估。"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine import runners
from app.models.review_run import ReviewRun, RuleExecution
from app.models.structure_profile import StructureProfile
from app.schemas.review_harness import (
    ReviewHarnessCase,
    ReviewHarnessCaseReport,
    ReviewHarnessEvidenceExpectation,
    ReviewHarnessManifest,
    ReviewHarnessReport,
    ReviewHarnessSource,
    ReviewHarnessViolationExpectation,
    ReviewHarnessViolationMatch,
)
from app.services.review import ReviewService


class ReviewHarnessService:
    """按清单评估既有 run，或在需要时创建并执行新 run。"""

    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def run(
        self,
        manifest: ReviewHarnessManifest,
        *,
        sources: dict[str, ReviewHarnessSource] | None = None,
    ) -> ReviewHarnessReport:
        reports: list[ReviewHarnessCaseReport] = []
        for case in manifest.cases:
            try:
                run_id = await self._prepare_run_id(case, sources or {})
                reports.append(await self._evaluate_run(case, run_id))
            except Exception as exc:
                reports.append(_error_report(case, exc))
        return aggregate_case_reports(reports, tenant_id=self.tenant_id)

    async def _prepare_run_id(
        self,
        case: ReviewHarnessCase,
        sources: dict[str, ReviewHarnessSource],
    ) -> int | None:
        if case.run_id is not None:
            return case.run_id
        source = sources.get(case.name)
        if source is None or case.rule_set_id is None:
            raise ValueError("新建 run 用例必须提供 artifact_dir、pdf_path 与 rule_set_id")
        run = await ReviewService(self.session, self.tenant_id).create_run(
            source.pdf_path.name,
            await asyncio.to_thread(source.pdf_path.read_bytes),
            created_by="review-harness",
        )
        await runners.execute_review(
            self.session,
            run_id=run.id,
            tenant_id=self.tenant_id,
            artifact_dir=source.artifact_dir,
            rule_set_id=case.rule_set_id,
        )
        return run.id

    async def _evaluate_run(
        self,
        case: ReviewHarnessCase,
        run_id: int | None,
    ) -> ReviewHarnessCaseReport:
        run = (
            (
                await self.session.execute(
                    select(ReviewRun).where(
                        ReviewRun.id == run_id,
                        ReviewRun.tenant_id == self.tenant_id,
                        ReviewRun.is_deleted.is_(False),
                    )
                )
            ).scalar_one_or_none()
            if run_id is not None
            else None
        )
        if run is None:
            return evaluate_case(
                case,
                run_id=run_id,
                run_status="missing",
                violations=[],
                rule_executions=[],
                bindings=[],
            )

        executions = (
            (
                await self.session.execute(
                    select(RuleExecution).where(RuleExecution.run_id == run.id)
                )
            )
            .scalars()
            .all()
        )
        profile = (
            await self._structure_profile(run.profile_id) if run.profile_id is not None else None
        )
        profile_data = dict(profile.profile or {}) if profile is not None else {}
        return evaluate_case(
            case,
            run_id=run.id,
            run_status=run.status,
            violations=list(run.violations or []),
            rule_executions=[
                {
                    "rule_code": item.rule_code,
                    "status": item.status,
                    "skip_reason": item.skip_reason,
                }
                for item in executions
            ],
            bindings=list(profile_data.get("bindings") or []),
            duration_ms=run.duration_ms,
            token_cost=run.token_cost,
        )

    async def _structure_profile(self, profile_id: int) -> StructureProfile | None:
        return (
            await self.session.execute(
                select(StructureProfile).where(
                    StructureProfile.id == profile_id,
                    StructureProfile.tenant_id == self.tenant_id,
                )
            )
        ).scalar_one_or_none()


def evaluate_case(
    case: ReviewHarnessCase,
    *,
    run_id: int | None,
    run_status: str,
    violations: list[dict[str, Any]],
    rule_executions: list[dict[str, Any]],
    bindings: list[dict[str, Any]],
    duration_ms: int = 0,
    token_cost: int = 0,
) -> ReviewHarnessCaseReport:
    """评估单个 run 的实际结果与期望差异。"""
    matched, missed, unexpected = _match_violations(case.expected_violations, violations)
    evidence_misses = _evaluate_evidence(case.expected_evidence, bindings)
    rule_status_counts = _status_counts(rule_executions)
    skipped_count = rule_status_counts.get("skipped", 0)
    failed_count = rule_status_counts.get("failed", 0)
    errors: list[str] = []
    if run_status != "completed":
        errors.append(f"run_status={run_status}")
    if missed:
        errors.append(f"missed_violations={len(missed)}")
    if evidence_misses:
        errors.append(f"evidence_misses={len(evidence_misses)}")
    if unexpected and not case.allow_extra_violations:
        errors.append(f"unexpected_violations={len(unexpected)}")
    if failed_count:
        errors.append(f"failed_rules={failed_count}")
    if case.fail_on_skipped and skipped_count:
        errors.append(f"skipped_rules={skipped_count}")

    return ReviewHarnessCaseReport(
        name=case.name,
        status="failed" if errors else "passed",
        run_id=run_id,
        error="；".join(errors) if errors else None,
        expected_violation_count=len(case.expected_violations),
        actual_violation_count=len(violations),
        matched_violation_count=len(matched),
        missed_violation_count=len(missed),
        unexpected_violation_count=len(unexpected),
        matched_violations=matched,
        missed_violations=missed,
        unexpected_violations=unexpected,
        evidence_expected_count=len(case.expected_evidence),
        evidence_found_count=len(case.expected_evidence) - len(evidence_misses),
        evidence_missing_count=len(evidence_misses),
        evidence_misses=evidence_misses,
        rule_status_counts=rule_status_counts,
        skipped_rule_count=skipped_count,
        failed_rule_count=failed_count,
        duration_ms=duration_ms,
        token_cost=token_cost,
    )


def aggregate_case_reports(
    reports: list[ReviewHarnessCaseReport],
    *,
    tenant_id: str = "",
) -> ReviewHarnessReport:
    """汇总用例报告为漏报 / 误报 / 证据缺失与成本指标。"""
    expected = sum(item.expected_violation_count for item in reports)
    actual = sum(item.actual_violation_count for item in reports)
    matched = sum(item.matched_violation_count for item in reports)
    missed = sum(item.missed_violation_count for item in reports)
    unexpected = sum(item.unexpected_violation_count for item in reports)
    precision = matched / actual if actual else 0.0
    recall = matched / expected if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    passed_count = sum(item.status == "passed" for item in reports)
    evidence_expected = sum(item.evidence_expected_count for item in reports)
    evidence_found = sum(item.evidence_found_count for item in reports)
    return ReviewHarnessReport(
        status="failed" if any(item.status == "failed" for item in reports) else "passed",
        tenant_id=tenant_id,
        case_total=len(reports),
        case_passed_count=passed_count,
        case_failed_count=len(reports) - passed_count,
        expected_violation_count=expected,
        actual_violation_count=actual,
        matched_violation_count=matched,
        missed_violation_count=missed,
        unexpected_violation_count=unexpected,
        precision=precision,
        recall=recall,
        f1=f1,
        evidence_expected_count=evidence_expected,
        evidence_found_count=evidence_found,
        evidence_missing_count=evidence_expected - evidence_found,
        skipped_rule_count=sum(item.skipped_rule_count for item in reports),
        failed_rule_count=sum(item.failed_rule_count for item in reports),
        total_duration_ms=sum(item.duration_ms for item in reports),
        total_token_cost=sum(item.token_cost for item in reports),
        cases=reports,
    )


def _match_violations(
    expected: list[ReviewHarnessViolationExpectation],
    actual: list[dict[str, Any]],
) -> tuple[
    list[ReviewHarnessViolationMatch],
    list[ReviewHarnessViolationExpectation],
    list[dict[str, Any]],
]:
    matches = _match_expected(expected, actual)
    used_indexes = {index for _, index in matches}
    matched = [match for match, _ in matches]
    # 一对一匹配后按对象 id 找回未匹配期望，避免同 rule_code 多条时期望被误删。
    matched_expected_ids = {id(match.expected) for match in matched}
    missed = [item for item in expected if id(item) not in matched_expected_ids]
    unexpected = [item for index, item in enumerate(actual) if index not in used_indexes]
    return matched, missed, unexpected


def _match_expected(
    expected: list[ReviewHarnessViolationExpectation],
    actual: list[dict[str, Any]],
) -> list[tuple[ReviewHarnessViolationMatch, int]]:
    best: list[tuple[ReviewHarnessViolationMatch, int]] = []

    def visit(
        expected_index: int,
        current: list[tuple[ReviewHarnessViolationMatch, int]],
        used: set[int],
    ) -> None:
        nonlocal best
        if expected_index == len(expected):
            if len(current) > len(best):
                best = list(current)
            return
        item = expected[expected_index]
        for index, candidate in enumerate(actual):
            if index in used or not _violation_matches(item, candidate):
                continue
            visit(
                expected_index + 1,
                [
                    *current,
                    (ReviewHarnessViolationMatch(expected=item, actual=candidate), index),
                ],
                {*used, index},
            )
        visit(expected_index + 1, current, used)

    visit(0, [], set())
    return best


def _violation_matches(
    expected: ReviewHarnessViolationExpectation,
    actual: dict[str, Any],
) -> bool:
    if str(actual.get("rule_id", "")) != expected.rule_code:
        return False
    if expected.title is not None and str(actual.get("title", "")) != expected.title:
        return False
    if expected.content_contains is not None and expected.content_contains not in str(
        actual.get("content", "")
    ):
        return False
    return not (expected.page_idx is not None and actual.get("page_idx") != expected.page_idx)


def _evaluate_evidence(
    expected: list[ReviewHarnessEvidenceExpectation],
    bindings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_concept = {
        str(item.get("concept_code", "")): item for item in bindings if isinstance(item, dict)
    }
    misses: list[dict[str, Any]] = []
    for item in expected:
        binding = by_concept.get(item.concept)
        quality, reason = _evidence_quality(binding)
        if not item.found:
            if reason == "found":
                misses.append({"concept": item.concept, "reason": "expected_missing_got_found"})
            continue
        if reason != "found":
            misses.append({"concept": item.concept, "reason": reason})
            continue
        if item.quality == "exact" and quality != "exact":
            misses.append({"concept": item.concept, "reason": f"expected_exact_got_{quality}"})
        elif item.quality == "weak" and quality not in {"exact", "weak"}:
            misses.append({"concept": item.concept, "reason": f"expected_weak_got_{quality}"})
    return misses


def _evidence_quality(binding: dict[str, Any] | None) -> tuple[str, str]:
    if binding is None:
        return "missing", "not_found"
    status = str(binding.get("status", ""))
    if status != "bound":
        return "missing", status or "unknown_status"
    targets = binding.get("targets")
    if not isinstance(targets, list) or not targets:
        return "missing", "empty_targets"
    if any(_has_stable_locator(target) for target in targets):
        return "exact", "found"
    if any(_has_page_hint(target) for target in targets):
        return "weak", "found"
    return "missing", "no_locator"


def _has_stable_locator(target: object) -> bool:
    if not isinstance(target, dict):
        return False
    locator = target.get("locator")
    if not isinstance(locator, dict):
        return False
    return any(
        key in locator and _non_empty(locator[key])
        for key in (
            "section_title_regex",
            "anchor_keywords",
            "field_aliases",
            "image_keywords",
            "after_section",
            "stop_keywords",
        )
    )


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


def _status_counts(executions: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in executions:
        status = str(item.get("status", "unknown"))
        result[status] = result.get(status, 0) + 1
    return result


def _error_report(case: ReviewHarnessCase, exc: Exception) -> ReviewHarnessCaseReport:
    return ReviewHarnessCaseReport(
        name=case.name,
        status="failed",
        run_id=case.run_id,
        error=str(exc),
        expected_violation_count=len(case.expected_violations),
        missed_violations=case.expected_violations,
        missed_violation_count=len(case.expected_violations),
        evidence_expected_count=len(case.expected_evidence),
        evidence_missing_count=len(case.expected_evidence),
    )
