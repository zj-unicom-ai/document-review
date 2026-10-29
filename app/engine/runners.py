# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""进程内审查执行编排：DB、本地 parser、LangGraph 与事件总线。"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import (
    resolve_tenant_storage_path,
    storage_display_path,
    tenant_storage_path,
)
from app.engine.cross_check import run_cross_check
from app.engine.document import DocumentContext
from app.engine.events import ReviewEventBus
from app.engine.evidence import resolve_profile_evidence
from app.engine.graph import ReviewDependencies, build_review_graph
from app.engine.planner import build_rule_plan, build_rule_plan_for_rules, select_rule_set
from app.engine.profile import build_profile, concept_set_hash
from app.engine.profile_discovery import ProfileDiscovery
from app.engine.state import FileRef, RulePlanItem
from app.integrations.llm import build_llm_service
from app.integrations.mineru import MineruArtifactParser
from app.models.concept import Concept
from app.models.review_run import ReviewRun, RuleExecution
from app.models.structure_profile import StructureProfile
from app.utils.pdf_sidebar_annotation import generate_sidebar_annotated_pdf


async def execute_review(
    session: AsyncSession,
    *,
    run_id: int,
    tenant_id: str,
    artifact_dir: Path,
    rule_set_id: int | None,
    rule_ids: Sequence[int] | None = None,
    event_bus: ReviewEventBus | None = None,
) -> ReviewRun:
    """执行一个已创建的 run，并把图结果完整写回数据库。"""
    started = time.monotonic()
    run = (
        await session.execute(
            select(ReviewRun).where(
                ReviewRun.id == run_id,
                ReviewRun.tenant_id == tenant_id,
                ReviewRun.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    source_path = resolve_tenant_storage_path(run.file_path, tenant_id, "uploads")
    parser = MineruArtifactParser(artifact_dir)
    profile_row: StructureProfile | None = None
    llm_service = build_llm_service(settings)

    def publish(tenant: str, run_key: str, event: str, data: dict[str, Any]) -> None:
        if event_bus is not None:
            event_bus.publish(tenant, run_key, event, data)

    async def persist_status(tenant: str, run_key: str, status: str) -> None:
        await session.execute(update(ReviewRun).where(ReviewRun.id == run_id).values(status=status))
        await session.commit()
        publish(tenant, run_key, "stage", {"status": status})

    async def parse_document(_state: dict[str, Any]):
        return await parser.parse(source_path)

    async def build_profile_callback(_state: dict[str, Any], doc: DocumentContext) -> dict:
        nonlocal profile_row
        concept_rows = (
            (
                await session.execute(
                    select(Concept).where(
                        Concept.is_deleted.is_(False),
                        Concept.tenant_id.in_(["", tenant_id]),
                    )
                )
            )
            .scalars()
            .all()
        )
        vocabulary = [
            {
                "concept_code": row.concept_code,
                "concept_name": row.concept_name,
                "aliases": row.aliases or [],
                "data_kind": row.data_kind,
            }
            for row in concept_rows
        ]
        concept_hash = concept_set_hash(vocabulary)
        discover = None
        if llm_service is not None and settings.llm_profile_discovery:

            async def discover(doc: DocumentContext):
                return await ProfileDiscovery(llm_service).discover(doc, vocabulary)

        profile_row = await build_profile(
            session,
            tenant_id,
            run.file_sha256,
            doc,
            source_run_id=run_id,
            discover=discover,
            concept_hash=concept_hash,
        )
        return resolve_profile_evidence(doc, vocabulary, dict(profile_row.profile))

    async def build_plan_callback(
        _state: dict[str, Any], _doc: DocumentContext, profile: dict[str, Any]
    ) -> list[RulePlanItem]:
        if rule_ids is not None:
            return await build_rule_plan_for_rules(session, tenant_id, rule_ids, profile)
        rule_set = await select_rule_set(session, tenant_id, rule_set_id, profile)
        return await build_rule_plan(session, tenant_id, rule_set, profile)

    async def annotate(state: dict[str, Any]) -> dict[str, Any]:
        output = _annotated_pdf_path(tenant_id, run_id)
        source = source_path

        def render_annotated() -> bytes:
            output.parent.mkdir(parents=True, exist_ok=True)
            return generate_sidebar_annotated_pdf(
                source.read_bytes(),
                state.get("aggregate").violations,
            )

        annotated = await asyncio.to_thread(render_annotated)
        await asyncio.to_thread(output.write_bytes, annotated)
        return {"annotated_pdf_path": storage_display_path(output)}

    async def persist_final(state: dict[str, Any]) -> None:
        duration_ms = int((time.monotonic() - started) * 1000)
        plan_rows = [_plan_item_row(item) for item in state.get("rule_plan") or []]
        aggregate = state.get("aggregate")
        error = state.get("error") or state.get("annotation_error")
        values: dict[str, Any] = {
            "status": "failed" if state.get("error") else "completed",
            "profile_id": profile_row.id if profile_row else None,
            "rule_plan": plan_rows,
            "violations": aggregate.violations if aggregate else [],
            "result": None if state.get("error") else aggregate.result,
            "summary": _summary_text(aggregate.summary if aggregate else {}),
            "annotated_pdf_path": state.get("annotated_pdf_path"),
            "error": error,
            "duration_ms": duration_ms,
        }
        token_cost = 0
        await session.execute(delete(RuleExecution).where(RuleExecution.run_id == run_id))
        for result in state.get("rule_results") or []:
            for entry in result.llm_io or []:
                usage = entry.get("usage") or {}
                token_cost += int(usage.get("input_tokens", 0))
                token_cost += int(usage.get("output_tokens", 0))
            session.add(
                RuleExecution(
                    run_id=run_id,
                    rule_id=result.rule_id,
                    rule_name=result.rule_name,
                    rule_code=result.rule_code,
                    rule_type=next(
                        item["rule_type"]
                        for item in plan_rows
                        if item["plan_item_id"] == result.plan_item_id
                    ),
                    status=result.status,
                    skip_reason=result.skip_reason,
                    violations=result.violations,
                    extracted=result.extracted,
                    tool_calls=result.tool_calls,
                    llm_io=result.llm_io,
                    error=result.error,
                    duration_ms=result.duration_ms,
                )
            )
        values["token_cost"] = token_cost
        await session.execute(update(ReviewRun).where(ReviewRun.id == run_id).values(**values))
        await session.commit()

    def close_events(
        tenant: str,
        run_key: str,
        error: str | None,
        result: str | None,
        violation_count: int,
    ) -> None:
        if event_bus is None:
            return
        if error is not None:
            event_bus.publish(tenant, run_key, "failed", {"error": error})
        else:
            event_bus.publish(
                tenant,
                run_key,
                "completed",
                {"result": result, "violation_count": violation_count},
            )
        event_bus.complete(tenant, run_key)

    deps = ReviewDependencies(
        parse_document=parse_document,
        build_profile=build_profile_callback,
        build_plan=build_plan_callback,
        annotate=annotate,
        persist_final=persist_final,
        publish_event=publish,
        persist_status=persist_status,
        close_events=close_events,
        llm_service=llm_service,
        cross_check=(
            (lambda results: run_cross_check(results, service=llm_service))
            if settings.cross_check_enabled and llm_service is not None
            else None
        ),
    )
    graph = build_review_graph(deps, checkpointer="memory")
    await graph.ainvoke(
        {
            "run_id": str(run_id),
            "tenant_id": tenant_id,
            "file": FileRef(run.file_path, run.file_name, run.file_sha256, run.file_size),
        },
        config={"configurable": {"thread_id": f"review-{run_id}"}},
    )
    await session.refresh(run)
    return run


async def fail_review_run(
    session: AsyncSession,
    *,
    run_id: int,
    tenant_id: str,
    error: str,
    event_bus: ReviewEventBus | None = None,
) -> None:
    """引擎级失败统一落库，并关闭 SSE consumer。"""
    run = await session.get(ReviewRun, run_id)
    if run is None or run.tenant_id != tenant_id:
        return
    run.status = "failed"
    run.result = None
    run.error = error[:2048]
    await session.commit()
    if event_bus is not None:
        event_bus.publish(tenant_id, str(run_id), "failed", {"error": run.error})
        event_bus.complete(tenant_id, str(run_id))


def _annotated_pdf_path(tenant_id: str, run_id: int) -> Path:
    """批注输出统一使用配置化 storage 根，避免依赖进程工作目录。"""
    return tenant_storage_path(tenant_id, "annotated", f"{run_id}.pdf")


def _plan_item_row(item: RulePlanItem) -> dict[str, Any]:
    row = asdict(item)
    row["rule_id"] = item.rule_id
    return row


def _summary_text(summary: dict[str, Any]) -> str:
    text = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    return text[:2048]
