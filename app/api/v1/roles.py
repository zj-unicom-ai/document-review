# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""租户内角色与菜单权限绑定 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import PageDeps
from app.core.deps import AuthorizedTenant, CurrentUser, DBSession, require_menu
from app.schemas.common import PageResult
from app.schemas.rbac import RoleCreate, RoleOut, RoleUpdate
from app.services.rbac import RbacService

router = APIRouter(dependencies=[Depends(require_menu("system_roles"))])


async def _role_out(service: RbacService, role, user_count: int | None = None) -> RoleOut:
    base = RoleOut.model_validate(role)
    base.menu_codes = await service.role_menu_codes(role)
    base.user_count = (
        user_count if user_count is not None else await service.role_user_count(role.id)
    )
    return base


@router.get("", response_model=PageResult[RoleOut])
async def list_roles(
    session: DBSession,
    tenant_id: AuthorizedTenant,
    page_deps: PageDeps,
):
    service = RbacService(session)
    roles, counts, total = await service.list_roles(
        tenant_id, page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q
    )
    return PageResult(
        items=[await _role_out(service, role, counts[role.id]) for role in roles],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
    current_user: CurrentUser,
):
    service = RbacService(session)
    role = await service.create_role(tenant_id, payload.model_dump(), actor=current_user.username)
    return await _role_out(service, role)


@router.get("/{role_id}", response_model=RoleOut)
async def get_role(role_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    service = RbacService(session)
    role = await service.get_role(tenant_id, role_id)
    return await _role_out(service, role)


@router.patch("/{role_id}", response_model=RoleOut)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
    current_user: CurrentUser,
):
    service = RbacService(session)
    role = await service.update_role(
        tenant_id, role_id, payload.model_dump(exclude_unset=True), actor=current_user.username
    )
    return await _role_out(service, role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    await RbacService(session).delete_role(tenant_id, role_id)
    return None
