# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Tenant management endpoints (super-admin protected)."""

from fastapi import APIRouter, Depends, status

from app.api.deps import PageDeps
from app.core.deps import DBSession, SuperAdmin, require_menu
from app.schemas.common import PageResult
from app.schemas.tenant import TenantCreate, TenantOut, TenantUpdate
from app.services.tenant import TenantService

router = APIRouter(dependencies=[Depends(require_menu("system_tenants"))])


@router.get("", response_model=PageResult[TenantOut])
async def list_tenants(_admin: SuperAdmin, session: DBSession, page_deps: PageDeps):
    svc = TenantService(session)
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[TenantOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, _admin: SuperAdmin, session: DBSession):
    svc = TenantService(session)
    obj = await svc.create(payload.model_dump())
    return TenantOut.model_validate(obj)


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(tenant_id: int, _admin: SuperAdmin, session: DBSession):
    svc = TenantService(session)
    return TenantOut.model_validate(await svc.get(tenant_id))


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: int, payload: TenantUpdate, _admin: SuperAdmin, session: DBSession
):
    svc = TenantService(session)
    return TenantOut.model_validate(
        await svc.update(tenant_id, payload.model_dump(exclude_unset=True))
    )


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: int, _admin: SuperAdmin, session: DBSession):
    svc = TenantService(session)
    await svc.delete(tenant_id)
    return None
