# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Operator registry: code-level operator implementations, DB-registered."""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin

RESULT_SEMANTICS = ("hit_is_violation", "hit_is_pass")


class Operator(Base, IdMixin, TimestampMixin):
    __tablename__ = "operators"

    op_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    applicable_data_kind: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    params_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    result_semantics: Mapped[str] = mapped_column(
        String(32), nullable=False, default="hit_is_violation"
    )
    executor: Mapped[str] = mapped_column(String(255), nullable=False)
    model_profile: Mapped[str | None] = mapped_column(String(32), nullable=True)
