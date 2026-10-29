# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""审查执行 API：上传、查询、计划与 SSE。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, or_, select

from app.api.deps import PageDeps
from app.core.db import get_sessionmaker
from app.core.deps import AuthorizedTenant, DBSession, require_menu
from app.core.exceptions import NotFoundError, ValidationError
from app.core.storage import resolve_tenant_storage_path, tenant_storage_path
from app.engine.events import ReviewEvent, ReviewEventBus
from app.engine.runners import execute_review, fail_review_run
from app.models.document_template import DocumentTemplate
from app.models.review_run import RuleExecution
from app.models.rule_set import RuleSet
from app.schemas.common import PageResult
from app.schemas.review_run import ReviewRunDetail, ReviewRunListItem, ReviewRunOut
from app.services.review import ReviewService
from app.utils.pdf_content_parse_utils import PDFParse

router = APIRouter(dependencies=[Depends(require_menu("reviews"))])

ReviewRunner = Callable[[int, str, str, int | None], Awaitable[None]]


async def _uploaded_review_runner(
    run_id: int,
    tenant_id: str,
    file_path: str,
    rule_set_id: int | None,
    *,
    mineru_parser: PDFParse | None = None,
) -> None:
    """上传 PDF 后生成 MinerU artifact，再进入结构化审查。"""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        run = await ReviewService(session, tenant_id).get(run_id)
        try:
            source_path = resolve_tenant_storage_path(file_path, tenant_id, "uploads")
            artifact_dir = tenant_storage_path(
                tenant_id,
                "artifacts",
                run.file_sha256,
                "extracted",
            )
            artifact_dir = await PDFParse.locate_or_build_artifact_async(
                source_path,
                output_dir=artifact_dir,
                parser=mineru_parser,
            )
            await execute_review(
                session,
                run_id=run_id,
                tenant_id=tenant_id,
                artifact_dir=artifact_dir,
                rule_set_id=rule_set_id,
                event_bus=review_event_bus,
            )
        except Exception as exc:
            await fail_review_run(
                session,
                run_id=run_id,
                tenant_id=tenant_id,
                error=str(exc),
                event_bus=review_event_bus,
            )


def _uploaded_review_runner_factory(*, mineru_parser: PDFParse | None = None) -> ReviewRunner:
    async def runner(run_id: int, tenant_id: str, file_path: str, rule_set_id: int | None) -> None:
        await _uploaded_review_runner(
            run_id,
            tenant_id,
            file_path,
            rule_set_id,
            mineru_parser=mineru_parser,
        )

    return runner


def get_review_runner() -> ReviewRunner:
    """后台 runner 注入点。"""
    return _uploaded_review_runner_factory()


review_event_bus = ReviewEventBus()
review_background_tasks: set[asyncio.Task[None]] = set()


def _rule_set_id_from_plan(run) -> int | None:
    """计划项 id 形如 "{rule_set_id}:{item_id}"，取前缀还原规则集。"""
    plan = run.rule_plan or []
    if not plan:
        return None
    raw = str((plan[0] or {}).get("plan_item_id", ""))
    head, _, _ = raw.partition(":")
    try:
        return int(head)
    except ValueError:
        return None


@router.get("", response_model=PageResult[ReviewRunListItem])
async def list_reviews(session: DBSession, tenant_id: AuthorizedTenant, page_deps: PageDeps):
    """当前租户的历史审查列表；规则集名来自计划快照关联。"""
    service = ReviewService(session, tenant_id)
    runs, total = await service.list_runs(page=page_deps.page, page_size=page_deps.page_size)
    set_ids = {sid for sid in (_rule_set_id_from_plan(run) for run in runs) if sid}
    names: dict[int, str] = {}
    if set_ids:
        rows = (
            await session.execute(
                select(RuleSet.id, RuleSet.name).where(
                    RuleSet.id.in_(set_ids),
                    or_(RuleSet.tenant_id == "", RuleSet.tenant_id == tenant_id),
                )
            )
        ).all()
        names = {row[0]: row[1] for row in rows}
    items = []
    for run in runs:
        item = ReviewRunListItem.model_validate(run)
        sid = _rule_set_id_from_plan(run)
        item.rule_set_name = names.get(sid) if sid else None
        items.append(item)
    return PageResult(items=items, total=total, page=page_deps.page, page_size=page_deps.page_size)


def get_event_bus() -> ReviewEventBus:
    """SSE 事件总线注入点。"""
    return review_event_bus


@router.post("", response_model=ReviewRunOut, status_code=201)
async def create_review(
    session: DBSession,
    tenant_id: AuthorizedTenant,
    runner: Annotated[ReviewRunner, Depends(get_review_runner)],
    file: Annotated[UploadFile, File()],
    rule_set_id: Annotated[int | None, Form()] = None,
):
    content = await file.read()
    if not content:
        raise ValidationError("上传文件不能为空")
    await _validate_rule_set_choice(session, tenant_id, rule_set_id)

    service = ReviewService(session, tenant_id)
    run = await service.create_run(file.filename or "", content)
    task = asyncio.create_task(runner(run.id, tenant_id, run.file_path, rule_set_id))
    review_background_tasks.add(task)
    task.add_done_callback(review_background_tasks.discard)
    return ReviewRunOut.model_validate(run)


@router.get("/{review_id}", response_model=ReviewRunDetail)
async def get_review(review_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    run = await ReviewService(session, tenant_id).get(review_id)
    detail = ReviewRunDetail.model_validate(run)
    detail.violations = run.violations or []
    return detail


@router.delete("/{review_id}", status_code=204)
async def delete_review(review_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    await ReviewService(session, tenant_id).delete_run(review_id)


@router.get("/{review_id}/plan")
async def get_review_plan(review_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    run = await ReviewService(session, tenant_id).get(review_id)
    return {"items": run.rule_plan or []}


@router.get("/{review_id}/annotated-pdf")
async def download_annotated_pdf(
    review_id: int,
    session: DBSession,
    tenant_id: AuthorizedTenant,
):
    """下载已完成审查的侧栏批注 PDF。"""
    run = await ReviewService(session, tenant_id).get(review_id)
    if not run.annotated_pdf_path:
        raise NotFoundError("批注 PDF 尚未生成")
    path = resolve_tenant_storage_path(run.annotated_pdf_path, tenant_id, "annotated")
    expected_path = tenant_storage_path(tenant_id, "annotated", f"{review_id}.pdf")
    if path != expected_path:
        raise ValidationError("批注 PDF 路径不合法")
    if not await asyncio.to_thread(path.is_file):
        raise NotFoundError("批注 PDF 文件不存在")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"review-{review_id}-annotated.pdf",
    )


@router.get("/{review_id}/rules/{rule_id}/trace")
async def get_rule_trace(
    review_id: int,
    rule_id: int,
    session: DBSession,
    tenant_id: AuthorizedTenant,
):
    """回放单条规则的模型 / 工具调用 trace（先做租户过滤）。"""
    # 先经 ReviewService 校验 run 对当前租户可见，再查执行行
    await ReviewService(session, tenant_id).get(review_id)
    execution = (
        await session.execute(
            select(RuleExecution).where(
                RuleExecution.run_id == review_id,
                RuleExecution.rule_id == rule_id,
            )
        )
    ).scalar_one_or_none()
    if execution is None:
        raise NotFoundError(f"规则执行记录不存在: rule_id={rule_id}")
    return {
        "rule_id": execution.rule_id,
        "rule_code": execution.rule_code,
        "rule_name": execution.rule_name,
        "rule_type": execution.rule_type,
        "status": execution.status,
        "skip_reason": execution.skip_reason,
        "violations": execution.violations or [],
        "tool_calls": execution.tool_calls or [],
        "llm_io": execution.llm_io or [],
        "error": execution.error,
        "duration_ms": execution.duration_ms,
    }


@router.get("/{review_id}/events")
async def get_review_events(
    review_id: int,
    session: DBSession,
    tenant_id: AuthorizedTenant,
    bus: Annotated[ReviewEventBus, Depends(get_event_bus)],
) -> StreamingResponse:
    run = await ReviewService(session, tenant_id).get(review_id)
    queue = bus.subscribe(tenant_id, str(review_id))
    if run.status in ("completed", "failed"):
        if run.status == "completed":
            bus.publish(
                tenant_id,
                str(review_id),
                "completed",
                {"result": run.result, "violation_count": len(run.violations or [])},
            )
        else:
            bus.publish(tenant_id, str(review_id), "failed", {"error": run.error or ""})
        bus.complete(tenant_id, str(review_id))

    async def stream() -> AsyncIterator[str]:
        try:
            while True:
                event = await queue.get()
                yield _sse(event)
                if event.event == "closed":
                    break
        finally:
            bus.unsubscribe(tenant_id, str(review_id), queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _validate_rule_set_choice(session, tenant_id: str, rule_set_id: int | None) -> None:
    if rule_set_id is not None:
        visible = (
            await session.execute(
                select(func.count())
                .select_from(RuleSet)
                .where(
                    RuleSet.id == rule_set_id,
                    or_(RuleSet.tenant_id == "", RuleSet.tenant_id == tenant_id),
                )
            )
        ).scalar_one()
        if not visible:
            raise ValidationError(f"规则集不存在或租户不可见: {rule_set_id}")
        return

    active_template_rows = (
        (
            await session.execute(
                select(DocumentTemplate.id).where(
                    DocumentTemplate.status == "active",
                    or_(
                        DocumentTemplate.tenant_id == "",
                        DocumentTemplate.tenant_id == tenant_id,
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    if not active_template_rows:
        raise ValidationError("未传 rule_set_id，且租户没有可用于自动绑定的 active 模板")

    linked_packs = (
        (
            await session.execute(
                select(RuleSet.template_id).where(
                    RuleSet.template_id.in_(active_template_rows),
                    or_(RuleSet.tenant_id == "", RuleSet.tenant_id == tenant_id),
                )
            )
        )
        .scalars()
        .all()
    )
    counts: dict[int, int] = {template_id: 0 for template_id in active_template_rows}
    for template_id in linked_packs:
        counts[template_id] += 1
    if any(count != 1 for count in counts.values()):
        raise ValidationError(
            "未传 rule_set_id，且 active 模板存在 0 个或多个规则集绑定；必须显式指定 rule_set_id"
        )


def _sse(event: ReviewEvent) -> str:
    return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"
