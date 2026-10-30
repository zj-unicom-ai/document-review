# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Structure profile contract (§6.3) - output of the profile node."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

BindingStatus = Literal["bound", "not_found", "ambiguous"]
TargetKind = Literal["section", "table", "image_group", "field", "item_list"]
DiscoveryMethod = Literal["template_match", "llm_discovery"]


class ConceptTarget(BaseModel):
    kind: TargetKind
    locator: dict[str, Any] = Field(default_factory=dict)
    page_idx: int | None = None
    page_idx_hint: int | None = None
    confidence: float = 1.0
    confirmed_by: str | None = None  # "template" | "llm" | "human"


class ConceptBinding(BaseModel):
    concept_code: str
    status: BindingStatus
    targets: list[ConceptTarget] = Field(default_factory=list)


class StructureProfile(BaseModel):
    """Output of the profile node, cached by file_sha256 + tenant template hash."""

    profile_id: str | None = None
    discovery_method: DiscoveryMethod
    template_id: int | None = None
    doc_summary: str | None = None
    bindings: list[ConceptBinding] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
