# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""算子: external_data_check - 外部数据核验"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from app.operators.base import OperatorBase, OperatorContext, OpResult
from app.operators.registry import register


class ExternalDataCheckParams(BaseModel):
    """external_data_check 算子参数。"""

    resource_key: str = Field(..., description="external_resource.resource_key")
    # 仅查询模式：把查询结果带回上下文供后续规则使用，不产生违规
    query: dict = Field(default_factory=dict, description="查询条件")
    # 核验模式：与外部登记值比对的文档字段；为空时退化为仅查询
    match_field: str | None = Field(default=None, description="要核验的字段名")
    fallback_value: str | None = None


@register
class ExternalDataCheck(OperatorBase):
    op_code: ClassVar[str] = "external_data_check"
    name: ClassVar[str] = "外部数据核验"
    description: ClassVar[str] = "查询外部登记数据并与文档信息比对，核验其真实性。"
    applicable_data_kind: ClassVar[list[str]] = ["field", "table", "item_list"]
    result_semantics: ClassVar[str] = "hit_is_violation"
    params_model: ClassVar[type[BaseModel]] = ExternalDataCheckParams

    def execute(self, ctx: OperatorContext, params: ExternalDataCheckParams) -> OpResult:
        if params.match_field:
            # 核验需要外部资源适配器；未配置时抛错交由 on_error_policy 兜底
            raise NotImplementedError("外部资源适配器未配置")
        # 仅查询模式：协议层先带回查询意图，真实取数由引擎集成层落地
        return OpResult(
            hit=False, extra={"resource_key": params.resource_key, "query": params.query}
        )
