# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Operator schemas (read-only after seed)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    op_code: str
    name: str
    description: str | None
    applicable_data_kind: list[str]
    params_schema: dict
    result_semantics: str
    executor: str
    model_profile: str | None
    created_at: datetime
    updated_at: datetime
