# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""算子: text_judge - 文本理解"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from app.operators.base import OperatorBase, OperatorContext, OpResult
from app.operators.registry import register


class JudgeViolation(BaseModel):
    """单条 LLM 业务命中。"""

    title: str = ""
    content: str = ""
    page_idx: int | None = None


class JudgeOutput(BaseModel):
    """LLM 理解类算子的 structured output 契约。"""

    violations: list[JudgeViolation] = []
    confidence: float | None = None
    reasoning: str = ""


class TextJudgeParams(BaseModel):
    """text_judge 算子参数。"""

    # 规则的自然语言检查描述是唯一核心配置；空描述直接拒绝（E6）
    instruction: str = Field(..., min_length=1)
    output_schema: dict[str, Any] = {}
    max_input_chars: int = 8000


@register
class TextJudge(OperatorBase):
    op_code: ClassVar[str] = "text_judge"
    name: ClassVar[str] = "文本理解"
    description: ClassVar[str] = (
        "阅读锚点锁定的文本内容（字段、表格、章节、全文等），按规则的自然语言描述"
        "判断是否合规，适合一切难以量化的内容检查。"
    )
    applicable_data_kind: ClassVar[list[str]] = [
        "field",
        "section",
        "image_group",
        "item_list",
        "table",
        "document",
    ]
    result_semantics: ClassVar[str] = "hit_is_violation"
    model_profile: ClassVar[str | None] = "text"
    params_model: ClassVar[type[BaseModel]] = TextJudgeParams

    async def execute(self, ctx: OperatorContext, params: TextJudgeParams) -> OpResult:
        if ctx.llm is None:
            raise RuntimeError("text_judge 需要 LLM 服务，但引擎未注入")
        context = {
            # 页码（0 基）供模型定位违规所在页；anchor 为检查对象绑定页
            "anchor_page_idx": ctx.anchor_page_idx,
            "table_page_idx": ctx.table_page_idx,
            "fields": ctx.fields,
            "table_rows": ctx.table_rows[:20],
            "sections": [
                {"title": section.get("title"), "page_idx": section.get("page_idx")}
                for section in ctx.sections[:50]
            ],
            "list_items": ctx.list_items[:20],
            "markdown_excerpt": ctx.markdown_text[:4000],
            "evidence": ctx.evidence,
        }
        call = await ctx.llm.call_structured(
            schema=JudgeOutput,
            system=(
                f"你是文档合规审查助手。任务：{params.instruction}\n"
                "受控上下文含页码信息（0 基）：anchor_page_idx 为检查对象所在页，"
                "sections 每项带 page_idx。输出违规时 page_idx 必须填写该问题内容"
                "实际所在页码（依据上下文页码判断，无法判断时用 anchor_page_idx）。\n"
                "只依据给定上下文判断，输出业务命中，不做规则字段装配。"
            ),
            messages=[
                {
                    "role": "user",
                    "content": "受控上下文：\n" + json.dumps(context, ensure_ascii=False),
                }
            ],
            model_profile=self.model_profile or "text",
            max_tokens=2000,
        )
        output: JudgeOutput = call.data
        return OpResult(
            hit=bool(output.violations),
            extra={
                "violations": [item.model_dump() for item in output.violations],
                "confidence": output.confidence,
                "reasoning": output.reasoning,
                "llm_trace": call.trace,
            },
        )
