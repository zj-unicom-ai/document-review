# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""菜单权限目录只读 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.deps import AuthorizedTenant, require_menu
from app.core.rbac import MENU_PERMISSIONS
from app.schemas.rbac import MenuPermissionOut

router = APIRouter(dependencies=[Depends(require_menu("system_roles"))])


@router.get("", response_model=list[MenuPermissionOut])
async def list_menu_permissions(_tenant_id: AuthorizedTenant) -> list[MenuPermissionOut]:
    return [MenuPermissionOut.model_validate(item) for item in MENU_PERMISSIONS]
