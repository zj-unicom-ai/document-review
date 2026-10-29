# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Rule CRUD (tenant-scoped; no version table, edit in place)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import PageDeps
from app.core.config import settings
from app.core.deps import AuthorizedTenant, DBSession, require_menu
from app.core.exceptions import ValidationError
from app.schemas.common import PageResult
from app.schemas.rule import (
    RuleCreate,
    RuleEnableResponse,
    RuleOut,
    RuleTrialResponse,
    RuleUpdate,
)
from app.services.rule import RuleService
from app.services.rule_trial import RuleTrialService

router = APIRouter(dependencies=[Depends(require_menu("rules"))])


@router.get("", response_model=PageResult[RuleOut])
async def list_rules(session: DBSession, tenant_id: AuthorizedTenant, page_deps: PageDeps):
    svc = RuleService(session, tenant_id)
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[RuleOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("/trial", response_model=RuleTrialResponse)
async def trial_rule(
    session: DBSession,
    tenant_id: AuthorizedTenant,
    rule: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    """用样例 PDF 调试一条未保存或编辑中的 structured 规则。"""
    max_bytes = settings.agent_max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content:
        raise ValidationError("上传文件不能为空")
    if len(content) > max_bytes:
        raise ValidationError("上传文件超过大小限制")
    try:
        payload = RuleCreate.model_validate_json(rule)
    except ValueError as exc:
        raise ValidationError("规则配置 JSON 不合法") from exc
    return await RuleTrialService(session, tenant_id).trial(payload, content)


@router.post("", response_model=RuleOut, status_code=status.HTTP_201_CREATED)
async def create_rule(payload: RuleCreate, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleService(session, tenant_id)
    obj = await svc.create(payload.model_dump())
    return RuleOut.model_validate(obj)


@router.get("/{rule_id}", response_model=RuleOut)
async def get_rule(rule_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleService(session, tenant_id)
    return RuleOut.model_validate(await svc.get(rule_id))


@router.patch("/{rule_id}", response_model=RuleOut)
async def update_rule(
    rule_id: int, payload: RuleUpdate, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = RuleService(session, tenant_id)
    return RuleOut.model_validate(await svc.update(rule_id, payload.model_dump(exclude_unset=True)))


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleService(session, tenant_id)
    await svc.delete(rule_id)
    return None


@router.post("/{rule_id}/enable", response_model=RuleEnableResponse)
async def enable_rule(rule_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleService(session, tenant_id)
    obj = await svc.set_enabled(rule_id, True)
    return RuleEnableResponse(id=obj.id, enabled=obj.enabled)


@router.post("/{rule_id}/disable", response_model=RuleEnableResponse)
async def disable_rule(rule_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleService(session, tenant_id)
    obj = await svc.set_enabled(rule_id, False)
    return RuleEnableResponse(id=obj.id, enabled=obj.enabled)
