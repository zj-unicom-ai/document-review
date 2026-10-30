# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""租户内用户管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.api.deps import PageDeps
from app.core.deps import AuthorizedTenant, CurrentUser, DBSession, require_menu
from app.schemas.common import PageResult
from app.schemas.rbac import UserCreate, UserOut, UserUpdate
from app.services.rbac import RbacService

router = APIRouter(dependencies=[Depends(require_menu("system_users"))])


def _user_out(user, roles) -> UserOut:
    base = UserOut.model_validate(user)
    base.roles = roles
    return base


@router.get("", response_model=PageResult[UserOut])
async def list_users(
    session: DBSession,
    tenant_id: AuthorizedTenant,
    page_deps: PageDeps,
):
    users, roles_by_user, total = await RbacService(session).list_users(
        tenant_id, page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q
    )
    return PageResult(
        items=[_user_out(user, roles_by_user[user.id]) for user in users],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
    current_user: CurrentUser,
):
    user, roles = await RbacService(session).create_user(
        tenant_id, payload.model_dump(), actor=current_user.username
    )
    return _user_out(user, roles)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(user_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    service = RbacService(session)
    user = await service.get_user(tenant_id, user_id)
    return _user_out(user, await service.user_roles(user))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
    current_user: CurrentUser,
):
    user, roles = await RbacService(session).update_user(
        tenant_id,
        user_id,
        payload.model_dump(exclude_unset=True),
        actor=current_user.username,
    )
    return _user_out(user, roles)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    session: DBSession,
    tenant_id: AuthorizedTenant,
    current_user: CurrentUser,
):
    await RbacService(session).delete_user(tenant_id, user_id, actor=current_user.username)
    return None
