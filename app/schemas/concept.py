# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Concept schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

DATA_KIND_VALUES = ("document", "section", "table", "field", "image_group", "item_list")
SOURCE_VALUES = ("platform", "tenant_custom")


class ConceptBase(BaseModel):
    concept_code: str = Field(min_length=1, max_length=64)
    concept_name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    aliases: list[str] = []
    data_kind: str = Field(default="field")
    source: str = Field(default="tenant_custom")
    seeded_from: str | None = None


class ConceptCreate(ConceptBase):
    pass


class ConceptUpdate(BaseModel):
    concept_name: str | None = None
    description: str | None = None
    aliases: list[str] | None = None
    data_kind: str | None = None


class ConceptOut(ConceptBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tenant_id: str
    created_at: datetime
    updated_at: datetime
