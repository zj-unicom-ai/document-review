# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""ExternalResource schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ResourceType = Literal["db_table", "file_csv", "file_xlsx", "http"]


class ExternalResourceBase(BaseModel):
    resource_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    resource_type: ResourceType
    config: dict[str, Any] = Field(default_factory=dict)
    schema_desc: str | None = None


class ExternalResourceCreate(ExternalResourceBase):
    pass


class ExternalResourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict[str, Any] | None = None
    schema_desc: str | None = None


class ExternalResourceOut(ExternalResourceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: datetime
