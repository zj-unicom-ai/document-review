# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Shared envelope types."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "ok"
    message: str = "ok"
    data: T | None = None


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=200)
    q: str | None = None


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class IdResponse(BaseModel):
    id: int


class TenantScoped(BaseModel):
    """Models that are tenant-scoped: tenant_id is set from the X-Tenant-Id header."""

    model_config = ConfigDict(from_attributes=True)
    tenant_id: str = ""
