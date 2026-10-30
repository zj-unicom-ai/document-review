# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""模板匹配画像与画像缓存。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.document import DocumentContext
from app.models.document_template import DocumentTemplate
from app.models.structure_profile import StructureProfile as StructureProfileRow
from app.schemas.profile import StructureProfile

# 画像发现输入结构变化时递增版本，用于自然失效历史画像缓存。
PROFILE_ALGORITHM_VERSION = "v5-content-image-group-alias"


def template_set_hash(templates: Sequence[DocumentTemplate | dict[str, Any]]) -> str:
    """按模板检测条件与绑定生成稳定内容哈希。"""
    payload: list[dict[str, Any]] = []
    for template in templates:
        if isinstance(template, dict):
            payload.append(
                {
                    "id": template.get("id", 0),
                    "detect_conditions": template.get("detect_conditions", []),
                    "concept_bindings": template.get("concept_bindings", []),
                }
            )
        else:
            payload.append(
                {
                    "id": template.id,
                    "detect_conditions": template.detect_conditions,
                    "concept_bindings": template.concept_bindings,
                }
            )
    serialized = json.dumps(
        {"algorithm_version": PROFILE_ALGORITHM_VERSION, "templates": payload},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def concept_set_hash(concepts: Sequence[dict[str, Any]]) -> str:
    """概念词表参与画像缓存键：检查对象改名 / 改别名后必须重建画像。"""
    payload = [
        {
            "concept_code": concept.get("concept_code", ""),
            "concept_name": concept.get("concept_name", ""),
            "aliases": concept.get("aliases") or [],
            "data_kind": concept.get("data_kind", ""),
        }
        for concept in concepts
    ]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def profile_cache_hash(template_hash: str, concept_hash: str | None) -> str:
    """组合画像缓存键；未传概念哈希的旧调用不参与新缓存命中。"""
    if concept_hash is None:
        return template_hash
    serialized = json.dumps(
        {"concept_set_hash": concept_hash, "template_set_hash": template_hash},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def _active_templates(session: AsyncSession, tenant_id: str) -> list[DocumentTemplate]:
    rows = (
        (
            await session.execute(
                select(DocumentTemplate)
                .where(
                    DocumentTemplate.status == "active",
                    or_(DocumentTemplate.tenant_id == "", DocumentTemplate.tenant_id == tenant_id),
                )
                .order_by(DocumentTemplate.id.asc())
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def find_profile(
    session: AsyncSession,
    tenant_id: str,
    file_sha256: str,
    *,
    concept_hash: str | None = None,
) -> StructureProfileRow | None:
    """按租户、文件哈希、当前模板集与概念词表哈希查缓存。"""
    templates = await _active_templates(session, tenant_id)
    current_hash = profile_cache_hash(template_set_hash(templates), concept_hash)
    return (
        await session.execute(
            select(StructureProfileRow)
            .where(
                StructureProfileRow.tenant_id == tenant_id,
                StructureProfileRow.file_sha256 == file_sha256,
                StructureProfileRow.template_set_hash == current_hash,
            )
            .order_by(StructureProfileRow.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def build_profile(
    session: AsyncSession,
    tenant_id: str,
    file_sha256: str,
    doc: DocumentContext,
    *,
    source_run_id: int | None = None,
    discover=None,
    concept_hash: str | None = None,
) -> StructureProfileRow:
    """生成并缓存画像；未命中模板时可用 LLM discovery，失败回退空绑定。"""
    cached = await find_profile(session, tenant_id, file_sha256, concept_hash=concept_hash)
    if cached is not None:
        return cached

    templates = await _active_templates(session, tenant_id)
    matched = [template for template in templates if _template_matches(template, doc)]
    matched.sort(key=lambda template: (-len(template.detect_conditions), template.id))
    selected = matched[0] if matched else None
    discovery_method = "template_match"
    llm_trace_id: str | None = None
    if selected is not None:
        contract = StructureProfile(
            discovery_method="template_match",
            template_id=selected.id,
            doc_summary=f"命中模板：{selected.name}",
            bindings=list(selected.concept_bindings),
            raw={"ambiguous_template_ids": [template.id for template in matched[1:]]},
        )
    else:
        raw: dict[str, Any] = {"ambiguous_template_ids": []}
        bindings: list = []
        doc_summary = "未命中 active 模板"
        if discover is not None:
            try:
                discovery = await discover(doc)
                bindings = discovery.bindings
                doc_summary = discovery.doc_summary
                discovery_method = "llm_discovery"
                llm_trace_id = discovery.trace_id
                raw["llm_trace_id"] = discovery.trace_id
                raw["llm_trace"] = discovery.trace
            except Exception as exc:
                raw["llm_discovery_error"] = str(exc)
        contract = StructureProfile(
            discovery_method=discovery_method,
            template_id=None,
            doc_summary=doc_summary,
            bindings=bindings,
            raw=raw,
        )
    row = StructureProfileRow(
        tenant_id=tenant_id,
        file_sha256=file_sha256,
        profile=contract.model_dump(mode="json"),
        template_set_hash=profile_cache_hash(template_set_hash(templates), concept_hash),
        discovery_method=discovery_method,
        template_id=selected.id if selected else None,
        llm_trace_id=llm_trace_id,
        source_run_id=source_run_id,
    )
    session.add(row)
    await session.commit()
    return row


async def load_profile_snapshot(
    session: AsyncSession,
    tenant_id: str,
    file_sha256: str,
    doc: DocumentContext,
    *,
    concept_hash: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """读取试跑画像快照；缓存可复用，未缓存时只做内存模板匹配。"""
    cached = await find_profile(session, tenant_id, file_sha256, concept_hash=concept_hash)
    if cached is not None:
        profile = dict(cached.profile)
        return profile, {
            "discovery_method": "cached_profile",
            "template_id": profile.get("template_id"),
        }

    templates = await _active_templates(session, tenant_id)
    matched = [template for template in templates if _template_matches(template, doc)]
    matched.sort(key=lambda template: (-len(template.detect_conditions), template.id))
    selected = matched[0] if matched else None
    if selected is None:
        contract = StructureProfile(
            discovery_method="template_match",
            template_id=None,
            doc_summary="未命中 active 模板",
            bindings=[],
            raw={"trial_only": True},
        )
    else:
        contract = StructureProfile(
            discovery_method="template_match",
            template_id=selected.id,
            doc_summary=f"命中模板：{selected.name}",
            bindings=list(selected.concept_bindings),
            raw={
                "ambiguous_template_ids": [item.id for item in matched[1:]],
                "trial_only": True,
            },
        )
    return contract.model_dump(mode="json"), {
        "discovery_method": "template_match" if selected is not None else "no_template",
        "template_id": selected.id if selected is not None else None,
    }


def _template_matches(template: DocumentTemplate, doc: DocumentContext) -> bool:
    return all(_condition_matches(condition, doc) for condition in template.detect_conditions)


def _condition_matches(condition: dict[str, Any], doc: DocumentContext) -> bool:
    condition_type = condition.get("type")
    markdown = doc.get_markdown()
    if condition_type == "section_title_regex":
        try:
            regex = re.compile(str(condition.get("pattern", "")))
        except re.error:
            return False
        return any(regex.search(str(section.get("title", ""))) for section in doc._sections)
    if condition_type == "md_contains":
        return str(condition.get("keyword", "")) in markdown
    if condition_type == "table_field_contains":
        field = _normalize(condition.get("field", ""))
        keywords = [str(value) for value in condition.get("keywords", [])]
        return (
            bool(field) and any(keyword in markdown for keyword in keywords) and field in markdown
        )
    return False


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or ""))
