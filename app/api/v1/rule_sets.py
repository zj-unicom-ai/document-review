# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""RuleSet + RuleSetItem CRUD."""

from fastapi import APIRouter, Depends, status

from app.api.deps import PageDeps
from app.core.deps import AuthorizedTenant, DBSession, require_menu
from app.schemas.common import PageResult
from app.schemas.rule_set import (
    RuleSetCreate,
    RuleSetItemsBulkUpdate,
    RuleSetOut,
    RuleSetTemplateCompatibilityOut,
    RuleSetUpdate,
)
from app.services.rule_set import RuleSetService
from app.services.rule_set_compatibility import RuleSetCompatibilityService

router = APIRouter(dependencies=[Depends(require_menu("rule_sets"))])


@router.get("", response_model=PageResult[RuleSetOut])
async def list_rule_sets(session: DBSession, tenant_id: AuthorizedTenant, page_deps: PageDeps):
    svc = RuleSetService(session, tenant_id)
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[RuleSetOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=RuleSetOut, status_code=status.HTTP_201_CREATED)
async def create_rule_set(payload: RuleSetCreate, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleSetService(session, tenant_id)
    obj = await svc.create(payload.model_dump())
    items = await svc._load_items(obj.id)
    obj.__dict__["items"] = list(items)  # type: ignore[attr-defined]
    return RuleSetOut.model_validate(obj)


@router.get("/{rule_set_id}", response_model=RuleSetOut)
async def get_rule_set(rule_set_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleSetService(session, tenant_id)
    return RuleSetOut.model_validate(await svc.get_with_items(rule_set_id))


@router.get(
    "/{rule_set_id}/template-compatibility",
    response_model=list[RuleSetTemplateCompatibilityOut],
)
async def get_rule_set_template_compatibility(
    rule_set_id: int,
    session: DBSession,
    tenant_id: AuthorizedTenant,
):
    """评估规则集 required anchor 与 active 模板绑定的兼容性。"""
    service = RuleSetCompatibilityService(session, tenant_id)
    return await service.analyze(rule_set_id)


@router.patch("/{rule_set_id}", response_model=RuleSetOut)
async def update_rule_set(
    rule_set_id: int, payload: RuleSetUpdate, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = RuleSetService(session, tenant_id)
    obj = await svc.update(rule_set_id, payload.model_dump(exclude_unset=True))
    items = await svc._load_items(obj.id)
    obj.__dict__["items"] = list(items)  # type: ignore[attr-defined]
    return RuleSetOut.model_validate(obj)


@router.delete("/{rule_set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule_set(rule_set_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = RuleSetService(session, tenant_id)
    await svc.delete(rule_set_id)
    return None


@router.put("/{rule_set_id}/items", response_model=RuleSetOut)
async def replace_rule_set_items(
    rule_set_id: int,
    payload: RuleSetItemsBulkUpdate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
):
    svc = RuleSetService(session, tenant_id)
    await svc.replace_items(rule_set_id, [it.model_dump() for it in payload.items])
    obj = await svc.get_with_items(rule_set_id)
    return RuleSetOut.model_validate(obj)
