# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""RBAC 用户、角色与菜单权限契约。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

USERNAME_PATTERN = r"^[a-zA-Z0-9_.-]+$"
ROLE_CODE_PATTERN = r"^[a-zA-Z0-9_-]+$"


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=USERNAME_PATTERN)
    display_name: str | None = Field(None, max_length=128)
    password: str = Field(min_length=8, max_length=128)
    role_ids: list[int] = Field(min_length=1)


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=128)
    status: str | None = Field(None, pattern="^(active|inactive)$")
    password: str | None = Field(None, min_length=8, max_length=128)
    role_ids: list[int] | None = Field(None, min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_code: str
    username: str
    display_name: str | None
    status: str
    roles: list[RoleBrief] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RoleCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=ROLE_CODE_PATTERN)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    menu_codes: list[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    status: str | None = Field(None, pattern="^(active|inactive)$")
    menu_codes: list[str] | None = None


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_code: str
    code: str
    name: str
    description: str | None
    is_system: bool
    status: str
    menu_codes: list[str] = Field(default_factory=list)
    user_count: int = 0
    created_at: datetime
    updated_at: datetime


class MenuPermissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    group: str
    assignable: bool
    parent: str | None = None
