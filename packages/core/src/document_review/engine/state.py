# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""引擎状态与结果契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from operator import add
from typing import Annotated, Any, TypedDict


@dataclass(frozen=True, slots=True)
class FileRef:
    """审查文件引用。"""

    path: str
    name: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class RulePlanItem:
    """一次 run 内不可变的规则计划快照。"""

    plan_item_id: str
    rule_id: int
    rule_code: str
    rule_name: str
    rule_type: str
    definition: dict[str, Any]
    binding: dict[str, Any] | None
    classify_id: int | None
    severity_default: str
    blocking_policy: str
    on_error_policy: str
    output_mode: str
    binding_status: str = "bound"
    skip_reason: str | None = None
    model_profile: str = "text"


@dataclass(slots=True)
class RuleResult:
    """单规则执行结果。"""

    plan_item_id: str
    rule_id: int
    rule_code: str
    rule_name: str
    status: str
    violations: list[dict[str, Any]] = field(default_factory=list)
    extracted: dict[str, Any] | None = None
    skip_reason: str | None = None
    error: str | None = None
    duration_ms: int = 0
    tool_calls: list[dict[str, Any]] | None = None
    llm_io: list[dict[str, Any]] | None = None

    def to_row(self) -> dict[str, Any]:
        """转换为可直接落库 / 持久化的字典。"""
        return {
            "plan_item_id": self.plan_item_id,
            "rule_id": self.rule_id,
            "rule_code": self.rule_code,
            "rule_name": self.rule_name,
            "status": self.status,
            "violations": self.violations,
            "extracted": self.extracted,
            "skip_reason": self.skip_reason,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "tool_calls": self.tool_calls,
            "llm_io": self.llm_io,
        }


@dataclass(frozen=True, slots=True)
class AggregateResult:
    """汇总后的最终契约。"""

    violations: list[dict[str, Any]]
    result: str
    summary: dict[str, Any]


class ReviewState(TypedDict, total=False):
    """LangGraph 顶层状态；节点可局部更新。"""

    run_id: str
    tenant_id: str
    file: FileRef
    parsed: Any
    profile: dict[str, Any] | None
    rule_plan: list[RulePlanItem]
    rule_results: Annotated[list[RuleResult], add]
    aggregate: AggregateResult | None
    annotated_pdf_path: str | None
    annotation_error: str | None
    error: str | None
