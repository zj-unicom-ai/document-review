# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Operator registry (read-only after seed)."""

from fastapi import APIRouter, Depends

from app.api.deps import PageDeps
from app.core.deps import DBSession, require_menu
from app.schemas.common import PageResult
from app.schemas.operator import OperatorOut
from app.services.operator import OperatorService

router = APIRouter(dependencies=[Depends(require_menu("operators"))])


@router.get("", response_model=PageResult[OperatorOut])
async def list_operators(session: DBSession, page_deps: PageDeps):
    svc = OperatorService(session, tenant_id="")
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[OperatorOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.get("/{op_id}", response_model=OperatorOut)
async def get_operator(op_id: int, session: DBSession):
    svc = OperatorService(session, tenant_id="")
    return OperatorOut.model_validate(await svc.get(op_id))
