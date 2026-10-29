# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""算子: vision_judge - 视觉理解"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from app.operators.base import OperatorBase, OperatorContext, OpResult
from app.operators.registry import register
from app.operators.text_judge import JudgeOutput


class VisionJudgeParams(BaseModel):
    """vision_judge 算子参数。"""

    # 一切视觉检查口径都由这句自然语言描述表达，平台不内置检查项
    instruction: str = Field(..., min_length=1)
    output_schema: dict[str, Any] = {}
    max_images: int = 5


@register
class VisionJudge(OperatorBase):
    op_code: ClassVar[str] = "vision_judge"
    name: ClassVar[str] = "视觉理解"
    description: ClassVar[str] = (
        "理解锚点锁定的图片内容，按规则的自然语言描述判断是否合规，并输出带位置的问题。"
    )
    applicable_data_kind: ClassVar[list[str]] = ["image_group"]
    result_semantics: ClassVar[str] = "hit_is_violation"
    model_profile: ClassVar[str | None] = "vision"
    params_model: ClassVar[type[BaseModel]] = VisionJudgeParams

    async def execute(self, ctx: OperatorContext, params: VisionJudgeParams) -> OpResult:
        if ctx.llm is None:
            raise RuntimeError("vision_judge 需要 LLM 服务，但引擎未注入")
        if not ctx.images:
            return OpResult(hit=False, extra={"violations": [], "reasoning": "无图片"})
        if ctx.get_image_bytes is None:
            raise RuntimeError("vision_judge 需要图片字节提取器，但引擎未注入")

        selected = ctx.images[: max(0, params.max_images)]
        images = [ctx.get_image_bytes(image) for image in selected]
        refs = [
            {key: image.get(key) for key in ("page_idx", "xref", "bbox_permille")}
            for image in selected
        ]
        call = await ctx.llm.call_structured(
            schema=JudgeOutput,
            system=(
                f"你是图片合规审查助手。任务：{params.instruction}\n"
                "按图片顺序输出业务命中；违规 page_idx 填写该图片引用中的页码"
                "（0 基）；无法确认时不输出违规。"
            ),
            messages=[
                {
                    "role": "user",
                    "content": "图片引用：\n" + json.dumps(refs, ensure_ascii=False),
                }
            ],
            model_profile=self.model_profile or "vision",
            images=images,
            max_tokens=2000,
        )
        output: JudgeOutput = call.data
        violations = []
        for idx, item in enumerate(output.violations):
            data = item.model_dump()
            if data.get("page_idx") is None and idx < len(selected):
                data["page_idx"] = selected[idx].get("page_idx", 0)
            violations.append(data)
        return OpResult(
            hit=bool(violations),
            extra={
                "violations": violations,
                "confidence": output.confidence,
                "reasoning": output.reasoning,
                "llm_trace": call.trace,
            },
        )
