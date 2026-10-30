# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""算子: extract_fields - 信息提取"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from app.operators.base import OperatorBase, OperatorContext, OpResult
from app.operators.registry import register


class ExtractFieldsParams(BaseModel):
    """extract_fields 算子参数。"""

    fields: list[dict[str, Any]] = Field(
        ..., description='[{name, aliases: [...], source?: "fields"|"table"}]'
    )
    output_key: str = Field(default="extracted")


@register
class ExtractFields(OperatorBase):
    op_code: ClassVar[str] = "extract_fields"
    name: ClassVar[str] = "信息提取"
    description: ClassVar[str] = "从文档中提取指定信息供后续检查使用，本身不产生违规结果。"
    applicable_data_kind: ClassVar[list[str]] = ["table", "field"]
    result_semantics: ClassVar[str] = "hit_is_violation"
    params_model: ClassVar[type[BaseModel]] = ExtractFieldsParams

    def execute(self, ctx: OperatorContext, params: ExtractFieldsParams) -> OpResult:
        out: dict[str, Any] = {}
        for spec in params.fields:
            name = spec.get("name")
            aliases = spec.get("aliases", [])
            source = spec.get("source", "fields")
            value = None
            if source == "table" and ctx.table_rows:
                for row in ctx.table_rows:
                    for a in aliases:
                        if a in row and str(row[a]).strip():
                            value = row[a]
                            break
                    if value is not None:
                        break
            else:
                for a in aliases:
                    if a in ctx.fields and ctx.fields[a].strip():
                        value = ctx.fields[a]
                        break
            out[name] = value
        return OpResult(hit=False, extra={params.output_key: out})
