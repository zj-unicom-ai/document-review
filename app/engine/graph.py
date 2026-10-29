# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""LangGraph 顶层审查图。"""

from __future__ import annotations

import operator
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.engine.aggregator import aggregate
from app.engine.cross_check import run_cross_check  # noqa: F401 - 供 runners 组装
from app.engine.document import DocumentContext
from app.engine.executor import run_rule
from app.engine.state import ReviewState, RulePlanItem, RuleResult
from app.integrations.llm import LlmService


async def _noop_status(tenant_id: str, run_id: str, status: str) -> None:
    """默认状态回调；测试与生产均显式注入真实实现。"""


@dataclass(slots=True)
class ReviewDependencies:
    """图运行的注入边界；生产与测试分别提供实现。"""

    parse_document: Callable[[dict[str, Any]], Awaitable[Any]]
    build_profile: Callable[[dict[str, Any], Any], Awaitable[dict[str, Any]]]
    build_plan: Callable[[dict[str, Any], Any, dict[str, Any]], Awaitable[list[RulePlanItem]]]
    annotate: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
    persist_final: Callable[[dict[str, Any]], Awaitable[None]]
    publish_event: Callable[[str, str, str, dict[str, Any]], None] = lambda *_: None
    persist_status: Callable[[str, str, str], Awaitable[None]] = _noop_status
    close_events: Callable[[str, str, str | None, str | None, int], None] = lambda *_: None
    llm_service: LlmService | None = None
    cross_check: Callable[[list[RuleResult]], Awaitable[list[dict[str, Any]] | None]] | None = None


def build_review_graph(
    deps: ReviewDependencies, *, checkpointer: MemorySaver | Literal["memory"] | None = None
):
    """编译 parse → profile → plan → Send fanout → aggregate → annotate → persist。"""
    builder = StateGraph(ReviewState)
    builder.add_node("parse", _parse_node(deps))
    builder.add_node("profile", _profile_node(deps))
    builder.add_node("plan", _plan_node(deps))
    builder.add_node("run_rule", _run_rule_node(deps))
    builder.add_node("aggregate", _aggregate_node(deps))
    builder.add_node("annotate", _annotate_node(deps))
    builder.add_node("persist", _persist_node(deps))

    builder.add_edge(START, "parse")
    builder.add_edge("parse", "profile")
    builder.add_edge("profile", "plan")
    builder.add_conditional_edges(
        "plan",
        _fanout,
        ["run_rule", "aggregate", "persist"],
    )
    builder.add_edge("run_rule", "aggregate")
    builder.add_edge("aggregate", "annotate")
    builder.add_edge("annotate", "persist")
    builder.add_edge("persist", END)

    saver = _memory_saver() if checkpointer == "memory" else checkpointer
    return builder.compile(checkpointer=saver)


def _parse_node(deps: ReviewDependencies):
    async def node(state: ReviewState) -> dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            await deps.persist_status(state["tenant_id"], state["run_id"], "parsing")
            parsed = await deps.parse_document(dict(state))
            return {"parsed": parsed}
        except Exception as exc:
            return {"error": str(exc)}

    return node


def _profile_node(deps: ReviewDependencies):
    async def node(state: ReviewState) -> dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            await deps.persist_status(state["tenant_id"], state["run_id"], "profiling")
            doc = DocumentContext(state["parsed"])
            profile = await deps.build_profile(dict(state), doc)
            return {"profile": profile}
        except Exception as exc:
            return {"error": str(exc)}

    return node


def _plan_node(deps: ReviewDependencies):
    async def node(state: ReviewState) -> dict[str, Any]:
        if state.get("error"):
            return {}
        try:
            await deps.persist_status(state["tenant_id"], state["run_id"], "planning")
            doc = DocumentContext(state["parsed"], state.get("profile") or {})
            plan = await deps.build_plan(dict(state), doc, state.get("profile") or {})
            deps.publish_event(
                state["tenant_id"], state["run_id"], "plan_ready", {"total": len(plan)}
            )
            return {"rule_plan": plan}
        except Exception as exc:
            return {"error": str(exc)}

    return node


def _fanout(state: ReviewState) -> Any:
    if state.get("error"):
        return "persist"
    plan = state.get("rule_plan") or []
    if not plan:
        return "aggregate"
    return [
        Send(
            "run_rule",
            {
                "run_id": state["run_id"],
                "tenant_id": state["tenant_id"],
                "plan_item": item,
                "parsed": state.get("parsed"),
                "profile": state.get("profile"),
            },
        )
        for item in plan
    ]


def _run_rule_node(deps: ReviewDependencies):
    async def node(payload: dict[str, Any]) -> dict[str, Any]:
        plan_item: RulePlanItem = payload["plan_item"]
        doc = DocumentContext(payload["parsed"], payload.get("profile") or {})
        result = await run_rule(plan_item, doc, llm_service=deps.llm_service)
        deps.publish_event(
            payload["tenant_id"],
            payload["run_id"],
            "rule_done",
            {
                "rule_code": result.rule_code,
                "status": result.status,
                "violation_count": len(result.violations),
            },
        )
        return {"rule_results": [result]}

    return node


def _aggregate_node(deps: ReviewDependencies):
    async def node(state: ReviewState) -> dict[str, Any]:
        extra: list[dict[str, Any]] | None = None
        if deps.cross_check is not None:
            extra = await deps.cross_check(state.get("rule_results") or [])
        return await _aggregate(state, extra)

    return node


async def _aggregate(state: ReviewState, extra: list[dict[str, Any]] | None) -> dict[str, Any]:
    results: list[RuleResult] = state.get("rule_results") or []
    expected = {item.plan_item_id for item in state.get("rule_plan") or []}
    actual = {result.plan_item_id for result in results}
    if expected != actual:
        raise RuntimeError(f"规则扇出结果不完整: expected={expected}, actual={actual}")
    return {"aggregate": aggregate(results, extra_violations=extra)}


def _annotate_node(deps: ReviewDependencies):
    async def node(state: ReviewState) -> dict[str, Any]:
        if state.get("error"):
            return {}
        snapshot = dict(state)
        snapshot["aggregate"] = state["aggregate"]
        try:
            await deps.persist_status(state["tenant_id"], state["run_id"], "aggregating")
            return await deps.annotate(snapshot)
        except Exception as exc:
            return {"annotation_error": str(exc)}

    return node


def _persist_node(deps: ReviewDependencies):
    async def node(state: ReviewState) -> dict[str, Any]:
        try:
            await deps.persist_final(dict(state))
            if state.get("error"):
                deps.close_events(state["tenant_id"], state["run_id"], state.get("error"), None, 0)
            else:
                aggregate_result = state["aggregate"]
                deps.close_events(
                    state["tenant_id"],
                    state["run_id"],
                    None,
                    aggregate_result.result,
                    len(aggregate_result.violations),
                )
        except Exception as exc:
            deps.close_events(state["tenant_id"], state["run_id"], str(exc), None, 0)
            return {"error": str(exc)}
        return {}

    return node


# StateGraph 需要标准 operator.add 作为列表归并 reducer。
_ = operator.add

_ALLOWED_MSGPACK_MODULES = (
    ("app.engine.state", "FileRef"),
    ("app.engine.state", "RulePlanItem"),
    ("app.engine.state", "RuleResult"),
    ("app.engine.state", "AggregateResult"),
    ("app.engine.document", "ParsedDocument"),
    ("document_review.engine.state", "FileRef"),
    ("document_review.engine.state", "RulePlanItem"),
    ("document_review.engine.state", "RuleResult"),
    ("document_review.engine.state", "AggregateResult"),
    ("document_review.engine.document", "ParsedDocument"),
)


def _memory_saver() -> MemorySaver:
    """显式允许本项目 checkpoint 状态类型，兼容 LangGraph 严格序列化。"""
    return MemorySaver(serde=JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK_MODULES))
