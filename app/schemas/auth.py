# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Authentication API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class AuthUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_code: str
    username: str
    display_name: str | None
    roles: list[str] = Field(default_factory=list)
    menu_codes: list[str] = Field(default_factory=list)
    status: str
    created_at: datetime
    updated_at: datetime
