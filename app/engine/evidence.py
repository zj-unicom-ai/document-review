# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""运行时确定性证据解析：模板提示优先，缺失 / 弱绑定动态兜底。"""

from __future__ import annotations

import re
from typing import Any

from app.engine.document import DocumentContext


def resolve_profile_evidence(
    doc: DocumentContext,
    concepts: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    """按章节标题与表格锚点补齐模板缺失或页级弱绑定。"""
    original_bindings = [dict(row) for row in profile.get("bindings") or []]
    by_code = {
        str(row.get("concept_code", "")): (index, row)
        for index, row in enumerate(original_bindings)
        if isinstance(row, dict)
    }
    bindings = list(original_bindings)
    resolution: dict[str, dict[str, str]] = {}

    for concept in concepts:
        code = str(concept.get("concept_code", ""))
        existing = by_code.get(code)
        if existing is not None and _has_stable_locator(existing[1]):
            continue

        replaced_quality = _existing_quality(existing[1] if existing else None)
        target = _resolve_target(doc, concept)
        if target is None:
            if existing is not None:
                resolution[code] = {
                    "strategy": "none",
                    "source": "runtime_resolver",
                    "replaced_quality": replaced_quality,
                }
            continue

        binding = {
            "concept_code": code,
            "status": "bound",
            "targets": [target],
        }
        if existing is None:
            bindings.append(binding)
        else:
            bindings[existing[0]] = binding
        resolution[code] = {
            "strategy": "section_title" if target["kind"] == "section" else "table_anchor",
            "source": "runtime_resolver",
            "replaced_quality": replaced_quality,
        }

    raw = dict(profile.get("raw") or {})
    if resolution:
        raw["evidence_resolution"] = resolution
    return {**profile, "bindings": bindings, "raw": raw}


def _resolve_target(doc: DocumentContext, concept: dict[str, Any]) -> dict[str, Any] | None:
    kind = str(concept.get("data_kind", "section"))
    if kind in {"table", "field", "item_list"}:
        return _resolve_table_target(
            doc,
            concept,
            field=kind == "field",
        )
    return _resolve_section_target(
        doc,
        concept,
        target_kind="image_group" if kind == "image_group" else "section",
    )


def _resolve_section_target(
    doc: DocumentContext,
    concept: dict[str, Any],
    *,
    target_kind: str,
) -> dict[str, Any] | None:
    sections = doc.get_section_tree(max_sections=500)
    for candidate in _candidates(concept):
        for section in sections:
            title = str(section.get("title", ""))
            if candidate and _compact(candidate) in _compact(title):
                return {
                    "kind": target_kind,
                    "locator": {"section_title_regex": re.escape(title)},
                    "page_idx": section.get("page_idx"),
                    "confidence": 0.9,
                    "confirmed_by": "runtime_resolver",
                }
    return None


def _resolve_table_target(
    doc: DocumentContext,
    concept: dict[str, Any],
    *,
    field: bool,
) -> dict[str, Any] | None:
    anchors = doc.get_table_anchors(max_anchors=500)
    candidates = _candidates(concept)
    for candidate in candidates:
        for anchor in anchors:
            text = _compact(str(anchor.get("text_excerpt", "")))
            if candidate and _compact(candidate) in text:
                return {
                    "kind": "field" if field else str(concept.get("data_kind", "table")),
                    "locator": {
                        "anchor_keywords": [candidate],
                        **(
                            {"field_aliases": _candidates(concept)}
                            if field
                            else {}
                            if str(concept.get("data_kind")) == "item_list"
                            else {
                                "block_idx": anchor.get("block_idx"),
                                "page_idx": anchor.get("page_idx"),
                            }
                        ),
                    },
                    "page_idx": anchor.get("page_idx"),
                    "confidence": 0.9,
                    "confirmed_by": "runtime_resolver",
                }
    return None


def _candidates(concept: dict[str, Any]) -> list[str]:
    values = [concept.get("concept_name"), *(concept.get("aliases") or [])]
    candidates = [str(value) for value in values if str(value).strip()]
    return sorted(dict.fromkeys(candidates), key=len, reverse=True)


def _has_stable_locator(binding: dict[str, Any]) -> bool:
    if str(binding.get("status", "")) != "bound":
        return False
    targets = binding.get("targets")
    if not isinstance(targets, list) or not targets:
        return False
    stable_keys = {
        "section_title_regex",
        "anchor_keywords",
        "field_aliases",
        "image_keywords",
        "after_section",
        "stop_keywords",
    }
    for target in targets:
        locator = target.get("locator") if isinstance(target, dict) else None
        if isinstance(locator, dict) and any(
            key in locator and _non_empty(locator[key]) for key in stable_keys
        ):
            return True
    return False


def _existing_quality(binding: dict[str, Any] | None) -> str:
    if binding is None:
        return "missing"
    if str(binding.get("status", "")) != "bound":
        return "missing"
    targets = binding.get("targets")
    if not isinstance(targets, list) or not targets:
        return "missing"
    return (
        "weak"
        if any(
            isinstance(target, dict)
            and (target.get("page_idx") is not None or target.get("page_idx_hint") is not None)
            for target in targets
        )
        else "missing"
    )


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _non_empty(value: object) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return value is not None
