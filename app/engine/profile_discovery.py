# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""画像 LLM 发现：未命中模板时的概念绑定识别。"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.engine.document import DocumentContext
from app.integrations.llm import LlmService
from app.schemas.profile import ConceptBinding


class DiscoveryTarget(BaseModel):
    """LLM 输出的单个绑定目标。"""

    kind: str
    locator: dict[str, Any] = Field(default_factory=dict)
    page_idx: int | None = None
    confidence: float = 0.8


class DiscoveryBinding(BaseModel):
    """LLM 输出的单概念绑定。"""

    concept_code: str
    targets: list[DiscoveryTarget] = Field(default_factory=list)


class ProfileDiscoveryOutput(BaseModel):
    """画像发现 structured output 契约。"""

    bindings: list[DiscoveryBinding] = Field(default_factory=list)
    doc_summary: str = ""
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """发现结果与 trace 引用。"""

    bindings: list[ConceptBinding]
    doc_summary: str
    trace_id: str
    trace: dict[str, Any]


class DiscoveryError(RuntimeError):
    """画像发现输出未通过校验。"""


class ProfileDiscovery:
    """LLM 画像发现服务。"""

    def __init__(self, service: LlmService):
        self.service = service

    async def discover(
        self, doc: DocumentContext, concepts: list[dict[str, Any]]
    ) -> DiscoveryResult:
        deterministic = [
            *_deterministic_table_bindings(doc, concepts),
            *_deterministic_image_bindings(doc, concepts),
        ]
        deterministic_codes = {item.concept_code for item in deterministic}
        vocabulary = {
            str(item.get("concept_code")): {
                "concept_name": item.get("concept_name"),
                "aliases": item.get("aliases") or [],
                "data_kind": item.get("data_kind"),
            }
            for item in concepts
        }
        payload = {
            "section_tree": doc.get_section_tree(),
            "table_anchors": doc.get_table_anchors(),
            "first_page_summary": doc.get_first_page_summary(),
            "concepts": vocabulary,
        }
        call = await self.service.call_structured(
            schema=ProfileDiscoveryOutput,
            system=(
                "你是文档结构分析助手。根据标题树、表格锚点和首页摘要，"
                "把概念绑定到文档目标；不确定就不要绑定。"
                "只输出词表内 concept_code。"
            ),
            messages=[
                {
                    "role": "user",
                    "content": "受控输入：\n" + json.dumps(payload, ensure_ascii=False),
                }
            ],
            model_profile="text",
            max_tokens=2000,
        )
        output: ProfileDiscoveryOutput = call.data
        bindings: list[ConceptBinding] = []
        for item in deterministic:
            bindings.append(
                ConceptBinding(
                    concept_code=item.concept_code,
                    status="bound",
                    targets=[target.model_dump() for target in item.targets],
                )
            )
        for item in output.bindings:
            if item.concept_code not in vocabulary:
                raise DiscoveryError(f"绑定 {item.concept_code} 未通过概念词表校验")
            if item.concept_code in deterministic_codes:
                continue
            bindings.append(
                ConceptBinding(
                    concept_code=item.concept_code,
                    status="bound",
                    targets=[target.model_dump() for target in item.targets],
                )
            )
        return DiscoveryResult(
            bindings=bindings,
            doc_summary=output.doc_summary or "LLM 画像发现",
            trace_id=uuid.uuid4().hex,
            trace=call.trace,
        )


def _deterministic_table_bindings(
    doc: DocumentContext, concepts: list[dict[str, Any]]
) -> list[DiscoveryBinding]:
    """按概念名 / 别名匹配表格文本，避免长复合表中 LLM 漏识别。"""
    result: list[DiscoveryBinding] = []
    anchors = doc.get_table_anchors()
    for concept in concepts:
        if concept.get("data_kind") != "table":
            continue
        aliases = [
            str(alias)
            for alias in [concept.get("concept_name"), *(concept.get("aliases") or [])]
            if str(alias).strip()
        ]
        for alias in sorted(aliases, key=len, reverse=True):
            compact_alias = _compact(alias)
            for anchor in anchors:
                if compact_alias in _compact(str(anchor.get("text_excerpt", ""))):
                    block_page = anchor.get("page_idx")
                    content_page = doc.locate_text_page(alias, fallback=block_page)
                    result.append(
                        DiscoveryBinding(
                            concept_code=str(concept.get("concept_code")),
                            targets=[
                                DiscoveryTarget(
                                    kind="table",
                                    page_idx=content_page,
                                    locator={
                                        "anchor_keywords": [alias],
                                        "block_idx": anchor.get("block_idx"),
                                        "page_idx": content_page,
                                    },
                                    confidence=0.9,
                                )
                            ],
                        )
                    )
                    break
            else:
                continue
            break
    return result


def _deterministic_image_bindings(
    doc: DocumentContext, concepts: list[dict[str, Any]]
) -> list[DiscoveryBinding]:
    """按概念名 / 别名定位邻近原 PDF 图片，避免 image_group 被章节标题吸附。"""
    result: list[DiscoveryBinding] = []
    for concept in concepts:
        if concept.get("data_kind") != "image_group":
            continue
        aliases = [
            str(alias)
            for alias in [concept.get("concept_name"), *(concept.get("aliases") or [])]
            if str(alias).strip()
        ]
        for alias in sorted(aliases, key=len, reverse=True):
            image = doc.locate_image_for_text(alias)
            if image is None:
                continue
            page_idx = int(image["page_idx"])
            result.append(
                DiscoveryBinding(
                    concept_code=str(concept.get("concept_code")),
                    targets=[
                        DiscoveryTarget(
                            kind="image_group",
                            page_idx=page_idx,
                            locator={
                                "anchor_keywords": [alias],
                                "image_xrefs": [int(image["xref"])],
                                "page_idx": page_idx,
                            },
                            confidence=0.9,
                        )
                    ],
                )
            )
            break
    return result


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)
