# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""structured / hybrid 确定性部分执行器。"""

from __future__ import annotations

import inspect
import re
import time
from typing import Any

from app.engine.document import DocumentContext
from app.engine.llm_rule import run_llm_rule
from app.engine.state import RulePlanItem, RuleResult
from app.engine.violation_builders import build_anomaly
from app.integrations.llm import LlmService
from app.operators.base import OpResult
from app.operators.registry import get_operator
from app.schemas.profile import ConceptBinding, ConceptTarget
from app.schemas.violation import Violation, ViolationMeta

_FULL_PARAM = re.compile(r"^\$\{([A-Za-z0-9_]+)\}$")
_EMBEDDED_PARAM = re.compile(r"\$\{([A-Za-z0-9_]+)\}")
_FULL_ITEM = re.compile(r"^\{\{item\.([A-Za-z0-9_]+)\}\}$")
_EMBEDDED_ITEM = re.compile(r"\{\{item\.([A-Za-z0-9_]+)\}\}")
_LLM_OPS = {"text_judge", "vision_judge"}


def resolve_placeholders(
    value: Any, params: dict[str, Any], item: dict[str, Any] | None = None
) -> Any:
    """递归解析规则参数与列表项字段占位符；完整占位符保留原始类型。"""
    if isinstance(value, str):
        full_param = _FULL_PARAM.fullmatch(value)
        if full_param and full_param.group(1) in params:
            return params[full_param.group(1)]
        full_item = _FULL_ITEM.fullmatch(value)
        if full_item and item and full_item.group(1) in item:
            return item[full_item.group(1)]

        def param_repl(match: re.Match[str]) -> str:
            value = params.get(match.group(1), match.group(0))
            # 字段清单等列表参数嵌入描述时渲染为顿号连接，避免 Python repr 泄漏到文案
            if isinstance(value, list):
                return "、".join(str(item) for item in value)
            return str(value)

        value = _EMBEDDED_PARAM.sub(param_repl, value)
        if item:

            def item_repl(match: re.Match[str]) -> str:
                return str(item.get(match.group(1), match.group(0)))

            value = _EMBEDDED_ITEM.sub(item_repl, value)
        return value
    if isinstance(value, dict):
        return {key: resolve_placeholders(child, params, item) for key, child in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(child, params, item) for child in value]
    return value


async def run_rule(
    plan: RulePlanItem,
    doc: DocumentContext,
    *,
    llm_service: LlmService | None = None,
) -> RuleResult:
    """执行一条规则快照，并保证单规则异常不影响调用方。"""
    started = time.monotonic()
    base = {
        "plan_item_id": plan.plan_item_id,
        "rule_id": plan.rule_id,
        "rule_code": plan.rule_code,
        "rule_name": plan.rule_name,
    }
    if plan.binding_status in ("not_found", "ambiguous") and plan.skip_reason:
        return RuleResult(**base, status="skipped", skip_reason=plan.skip_reason)
    if plan.rule_type == "llm":
        return await run_llm_rule(plan, doc, llm_service)

    violations: list[dict[str, Any]] = []
    extracted: dict[str, Any] | None = None
    llm_io: list[dict[str, Any]] = []
    try:
        binding = _binding_for_plan(plan, doc)
        ctx = doc.to_operator_context(binding)
        ctx.llm = llm_service
        ctx.get_image_bytes = doc.get_image_bytes
        definition = plan.definition
        ctx.evidence = doc.build_evidence_context(definition.get("evidence"))
        top_params = resolve_placeholders(
            definition.get("params", {}), definition.get("params", {})
        )

        async def run_ops(ops: list[dict[str, Any]], item: dict[str, Any] | None = None) -> None:
            nonlocal extracted
            for op_config in ops:
                if op_config.get("op") == "list_for_each":
                    raw_params = resolve_placeholders(op_config.get("params", {}), top_params, item)
                    validated = operator_cls_for(op_config).params_model.model_validate(raw_params)
                    # 逐项遍历画像提取的结构化清单；占位符 {{item.字段}} 引用当前项。
                    # 清单是文档级数据，不依赖锚点 kind 的上下文装配差异。
                    for current in doc.get_list_items(binding):
                        for child_config in validated.child_ops:
                            if (
                                child_config.get("op") in _LLM_OPS
                                and top_params.get("llm_review", True) is False
                            ):
                                continue
                            child_result = await _execute_op(child_config, ctx, top_params, current)
                            if _is_violation(child_config, child_result):
                                violations.append(
                                    _build_violation(
                                        plan, binding, child_config, child_result, current
                                    )
                                )
                    continue
                if op_config.get("op") in _LLM_OPS and top_params.get("llm_review", True) is False:
                    continue
                op_result = await _execute_op(op_config, ctx, top_params, item)
                if op_config.get("op") == "extract_fields":
                    extracted = dict(op_result.extra.get("extracted", op_result.extra))
                if op_result.extra.get("llm_trace"):
                    llm_io.append(op_result.extra["llm_trace"])
                if _is_violation(op_config, op_result):
                    violations.extend(
                        _build_op_violations(plan, binding, op_config, op_result, item)
                    )

        iterate = definition.get("iterate")
        if iterate:
            for item in doc.get_list_items(binding):
                await run_ops(definition.get("ops", []), item)
        else:
            await run_ops(definition.get("ops", []))

        return RuleResult(
            **base,
            status="success",
            violations=violations,
            extracted=extracted,
            duration_ms=int((time.monotonic() - started) * 1000),
            llm_io=llm_io or None,
        )
    except Exception as exc:
        if plan.on_error_policy == "skip":
            return RuleResult(
                **base,
                status="skipped",
                skip_reason="operator_error_skipped",
                violations=violations,
                extracted=extracted,
                error=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        if plan.on_error_policy == "fail_run":
            return RuleResult(
                **base,
                status="failed",
                violations=violations,
                extracted=extracted,
                error=str(exc),
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        anomaly = build_anomaly(plan, str(exc))
        return RuleResult(
            **base,
            status="fallback_annotated",
            violations=[*violations, anomaly],
            extracted=extracted,
            error=str(exc),
            duration_ms=int((time.monotonic() - started) * 1000),
        )


async def _execute_op(
    op_config: dict[str, Any],
    ctx: Any,
    top_params: dict[str, Any],
    item: dict[str, Any] | None,
) -> OpResult:
    operator_cls = operator_cls_for(op_config)
    raw_params = resolve_placeholders(op_config.get("params", {}), top_params, item)
    validated = operator_cls.params_model.model_validate(raw_params)
    result = operator_cls().execute(ctx, validated)
    # LLM 算子是 async；结构化算子保持同步路径
    if inspect.isawaitable(result):
        return await result
    return result


def _build_op_violations(
    plan: RulePlanItem,
    binding: ConceptBinding,
    op_config: dict[str, Any],
    op_result: OpResult,
    item: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """LLM 命中逐条装配；普通算子仍走单一 fail 模板。"""
    llm_items = op_result.extra.get("violations")
    if op_config.get("op") in _LLM_OPS and isinstance(llm_items, list):
        return [
            _build_violation(
                plan,
                binding,
                op_config,
                op_result,
                item,
                llm_item=item if isinstance(item, dict) else {},
            )
            for item in llm_items
        ]
    return [_build_violation(plan, binding, op_config, op_result, item)]


def operator_cls_for(op_config: dict[str, Any]):
    operator_cls = get_operator(op_config["op"])
    if operator_cls is None:
        raise ValueError(f"unknown operator: {op_config['op']}")
    return operator_cls


def _is_violation(op_config: dict[str, Any], op_result: OpResult) -> bool:
    operator_cls = get_operator(op_config["op"])
    semantics = operator_cls.result_semantics if operator_cls else "hit_is_violation"
    return (semantics == "hit_is_violation" and op_result.hit) or (
        semantics == "hit_is_pass" and not op_result.hit
    )


def _build_violation(
    plan: RulePlanItem,
    binding: ConceptBinding,
    op_config: dict[str, Any],
    op_result: OpResult,
    item: dict[str, Any] | None,
    llm_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fail = resolve_placeholders(
        op_config.get("fail", {}),
        plan.definition.get("params", {}),
        item,
    )
    target_page = binding.targets[0].page_idx if binding.targets else None
    severity = fail.get("severity", plan.severity_default)
    observation = plan.blocking_policy == "observation"
    confidence = op_result.extra.get("confidence")
    if confidence is None and binding.targets:
        confidence = binding.targets[0].confidence
    meta = ViolationMeta(
        blocking=severity not in ("提醒",)
        and plan.blocking_policy not in ("advise", "observation"),
        confidence=confidence,
        observation=observation,
        # 契约字段沿用 item_no，语义为“列表项编号”（违规输出契约本次不变）
        item_no=(str(item.get("no")) if item and item.get("no") is not None else None),
        extra={
            key: value
            for key, value in op_result.extra.items()
            if key not in ("violations", "llm_trace")
        },
    )
    llm_title = (llm_item or {}).get("title")
    llm_content = (llm_item or {}).get("content")
    llm_page = (llm_item or {}).get("page_idx")
    violation = Violation(
        rule_id=plan.rule_code,
        rule_name=plan.rule_name,
        classify_id=int(fail.get("classify_id", plan.classify_id or 0)),
        title=str(llm_title or fail.get("title", plan.rule_name)),
        severity=severity,
        content=str(llm_content or fail.get("content", "")),
        page_idx=int(
            llm_page
            if llm_page is not None
            else fail.get("page_idx", target_page if target_page is not None else 0)
        ),
        mark_text=list(fail.get("mark_text", [])),
        meta=meta,
    )
    return violation.model_dump(mode="json")


def _binding_for_plan(plan: RulePlanItem, doc: DocumentContext) -> ConceptBinding:
    resolved = doc.resolve(plan.definition["anchor"]["concept"])
    if resolved is not None:
        return resolved
    if isinstance(plan.binding, ConceptBinding):
        return plan.binding
    if plan.binding:
        return ConceptBinding.model_validate(plan.binding)
    anchor = plan.definition["anchor"]
    return ConceptBinding(
        concept_code=anchor.get("concept", ""),
        status="bound",
        targets=[
            ConceptTarget(
                kind="field",
                locator=anchor.get("locator", {}),
            )
        ],
    )
