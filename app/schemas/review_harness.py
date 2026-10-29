# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Review Harness 清单与报告契约。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class ReviewHarnessViolationExpectation(BaseModel):
    """期望违规；rule_code 必配，其余字段用于收紧匹配。"""

    rule_code: str
    title: str | None = None
    content_contains: str | None = None
    page_idx: int | None = None


class ReviewHarnessEvidenceExpectation(BaseModel):
    """期望概念证据与最低定位质量。"""

    concept: str
    found: bool = True
    quality: Literal["any", "exact", "weak"] = "any"


class ReviewHarnessCase(BaseModel):
    """单个 Harness 用例。"""

    name: str
    run_id: int | None = None
    artifact_dir: str | None = None
    pdf_path: str | None = None
    rule_set_id: int | None = None
    expected_violations: list[ReviewHarnessViolationExpectation] = []
    expected_evidence: list[ReviewHarnessEvidenceExpectation] = []
    allow_extra_violations: bool = False
    fail_on_skipped: bool = True


class ReviewHarnessManifest(BaseModel):
    """一次 Harness 执行的输入清单。"""

    tenant_id: str
    cases: list[ReviewHarnessCase] = Field(min_length=1)


class ReviewHarnessSource(BaseModel):
    """CLI / 测试传入的新建 run 源文件。"""

    artifact_dir: Path
    pdf_path: Path


class ReviewHarnessViolationMatch(BaseModel):
    """期望违规与实际违规的一对一匹配结果。"""

    expected: ReviewHarnessViolationExpectation
    actual: dict[str, Any]


class ReviewHarnessCaseReport(BaseModel):
    """单用例评估结果。"""

    name: str
    status: Literal["passed", "failed"]
    run_id: int | None
    error: str | None = None
    expected_violation_count: int = 0
    actual_violation_count: int = 0
    matched_violation_count: int = 0
    missed_violation_count: int = 0
    unexpected_violation_count: int = 0
    matched_violations: list[ReviewHarnessViolationMatch] = []
    missed_violations: list[ReviewHarnessViolationExpectation] = []
    unexpected_violations: list[dict[str, Any]] = []
    evidence_expected_count: int = 0
    evidence_found_count: int = 0
    evidence_missing_count: int = 0
    evidence_misses: list[dict[str, Any]] = []
    rule_status_counts: dict[str, int] = {}
    skipped_rule_count: int = 0
    failed_rule_count: int = 0
    duration_ms: int = 0
    token_cost: int = 0


class ReviewHarnessReport(BaseModel):
    """整体回归报告。"""

    status: Literal["passed", "failed"]
    tenant_id: str
    case_total: int
    case_passed_count: int
    case_failed_count: int
    expected_violation_count: int
    actual_violation_count: int
    matched_violation_count: int
    missed_violation_count: int
    unexpected_violation_count: int
    precision: float
    recall: float
    f1: float
    evidence_expected_count: int
    evidence_found_count: int
    evidence_missing_count: int
    skipped_rule_count: int
    failed_rule_count: int
    total_duration_ms: int
    total_token_cost: int
    cases: list[ReviewHarnessCaseReport]
