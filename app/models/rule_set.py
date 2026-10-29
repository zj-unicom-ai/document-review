# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""RuleSet: bundle of rules with order, enable, and params overrides."""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditMixin, Base, IdMixin, TenantMixin, TimestampMixin


class RuleSet(Base, IdMixin, TenantMixin, AuditMixin):
    __tablename__ = "rule_sets"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    template_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_templates.id"), nullable=True, index=True
    )
    is_standard_pack: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default=text("0")
    )
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)


class RuleSetItem(Base, IdMixin, TimestampMixin):
    __tablename__ = "rule_set_items"

    rule_set_id: Mapped[int] = mapped_column(
        ForeignKey("rule_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_id: Mapped[int] = mapped_column(ForeignKey("rules.id"), nullable=False, index=True)
    execution_order: Mapped[int] = mapped_column(nullable=False, default=0)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=text("1"))
    # params_override only changes params values; engine validates shape.
    params_override: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
