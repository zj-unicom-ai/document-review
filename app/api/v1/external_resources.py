# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""External resource CRUD (Doris / xlsx / csv / http)."""

from fastapi import APIRouter, Depends, status

from app.api.deps import PageDeps
from app.core.deps import AuthorizedTenant, DBSession, require_menu
from app.schemas.common import PageResult
from app.schemas.external_resource import (
    ExternalResourceCreate,
    ExternalResourceOut,
    ExternalResourceUpdate,
)
from app.services.external_resource import ExternalResourceService

router = APIRouter(dependencies=[Depends(require_menu("system_resources"))])


@router.get("", response_model=PageResult[ExternalResourceOut])
async def list_resources(session: DBSession, tenant_id: AuthorizedTenant, page_deps: PageDeps):
    svc = ExternalResourceService(session, tenant_id)
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[ExternalResourceOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=ExternalResourceOut, status_code=status.HTTP_201_CREATED)
async def create_resource(
    payload: ExternalResourceCreate, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = ExternalResourceService(session, tenant_id)
    obj = await svc.create(payload.model_dump())
    return ExternalResourceOut.model_validate(obj)


@router.get("/{resource_id}", response_model=ExternalResourceOut)
async def get_resource(resource_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = ExternalResourceService(session, tenant_id)
    return ExternalResourceOut.model_validate(await svc.get(resource_id))


@router.patch("/{resource_id}", response_model=ExternalResourceOut)
async def update_resource(
    resource_id: int,
    payload: ExternalResourceUpdate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
):
    svc = ExternalResourceService(session, tenant_id)
    return ExternalResourceOut.model_validate(
        await svc.update(resource_id, payload.model_dump(exclude_unset=True))
    )


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resource(resource_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = ExternalResourceService(session, tenant_id)
    await svc.delete(resource_id)
    return None
