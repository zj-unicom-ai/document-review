# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Login session APIs for the platform console."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.config import settings
from app.core.deps import CurrentUser, DBSession
from app.core.security import create_session_token
from app.schemas.auth import AuthLoginRequest, AuthUserOut
from app.services.rbac import RbacService
from app.services.user import UserService

router = APIRouter()
SESSION_COOKIE_NAME = "document_review_session"


@router.post("/login", response_model=AuthUserOut)
async def login(payload: AuthLoginRequest, response: Response, session: DBSession) -> AuthUserOut:
    user = await UserService(session).authenticate(payload.username.strip(), payload.password)
    rbac = RbacService(session)

    token = create_session_token(user_id=user.id, username=user.username)
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.auth_session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.app_env == "production",
    )
    return await _auth_out(rbac, user)


async def _auth_out(rbac: RbacService, user) -> AuthUserOut:
    base = AuthUserOut.model_validate(user)
    base.roles = await rbac.role_codes(user)
    base.menu_codes = await rbac.menu_codes(user)
    return base


@router.get("/me", response_model=AuthUserOut)
async def me(current_user: CurrentUser, session: DBSession) -> AuthUserOut:
    rbac = RbacService(session)
    return await _auth_out(rbac, current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)
    return None
