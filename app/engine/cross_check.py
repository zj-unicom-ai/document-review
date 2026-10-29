# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""可选 cross_check：light 模型复核全部规则结果，仅产出观察项。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from app.engine.state import RuleResult
from app.engine.violation_builders import build_llm_violation
from app.integrations.llm import LlmService


class CrossCheckObservation(BaseModel):
    """单条交叉复核观察。"""

    rule_code: str = ""
    title: str
    content: str
    page_idx: int = 0
    confidence: float | None = None


class CrossCheckOutput(BaseModel):
    """cross_check structured output 契约。"""

    observations: list[CrossCheckObservation] = Field(default_factory=list)
    reasoning: str = ""


class _CrossPlan:
    """复用 build_llm_violation 所需的最小 plan 形状。"""

    rule_code = "CROSS-CHECK"
    rule_name = "交叉复核观察项"
    classify_id = 0
    severity_default = "提醒"
    blocking_policy = "observation"


async def run_cross_check(
    results: list[RuleResult], *, service: LlmService
) -> list[dict[str, Any]] | None:
    """执行交叉复核；任何失败都静默返回 None，不影响 run。"""
    try:
        summary = [
            {
                "rule_code": result.rule_code,
                "status": result.status,
                "violations": [
                    {
                        "title": violation.get("title"),
                        "content": violation.get("content"),
                        "page_idx": violation.get("page_idx"),
                    }
                    for violation in result.violations
                ],
            }
            for result in results
        ]
        call = await service.call_structured(
            schema=CrossCheckOutput,
            system=(
                "你是审查结果交叉复核助手。基于各规则结果摘要，只输出疑似"
                "规则拆分注水、模板套用或内容矛盾的观察项；不得输出阻断性结论。"
            ),
            messages=[
                {
                    "role": "user",
                    "content": "规则结果摘要：\n" + json.dumps(summary, ensure_ascii=False),
                }
            ],
            model_profile="light",
            max_tokens=1600,
        )
        output: CrossCheckOutput = call.data
        violations: list[dict[str, Any]] = []
        for item in output.observations:
            violation = build_llm_violation(
                _CrossPlan(),  # type: ignore[arg-type]
                item.model_dump(),
                confidence=item.confidence,
                reasoning=output.reasoning,
            )
            violation["meta"]["extra"]["target_rule_code"] = item.rule_code
            violations.append(violation)
        return violations
    except Exception:
        return None
