# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Classification schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClassificationBase(BaseModel):
    classify_id: int = Field(ge=0, le=99999)
    parent_id: int | None = None
    level: int = Field(default=2, ge=1, le=4)
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    sort_order: int = 0


class ClassificationCreate(ClassificationBase):
    pass


class ClassificationUpdate(BaseModel):
    """分类更新契约；level 由 parent_id 推导，不允许客户端直接声明。"""

    classify_id: int | None = Field(default=None, ge=0, le=99999)
    parent_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    sort_order: int | None = None


class ClassificationDeletePreview(BaseModel):
    """删除影响预览；计数在 DELETE 时会重新查询。"""

    classification_count: int
    child_count: int
    rule_count: int


class ClassificationOut(ClassificationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: datetime
