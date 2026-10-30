# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""算子: list_for_each - 清单逐条核查"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import BaseModel, Field

from app.operators.base import OperatorBase
from app.operators.registry import register


class ListForEachParams(BaseModel):
    """list_for_each 算子参数。"""

    child_ops: list[dict[str, Any]] = Field(..., description="[{op, params, fail}]")
    # 子算子参数中可用 {{item.字段}} 引用当前列表项的值
    child_params_from_item: list[str] = Field(default_factory=list)


@register
class ListForEach(OperatorBase):
    """对画像提取的结构化清单逐项执行子检查。

    展开逻辑由引擎执行器承担：每个列表项作为上下文执行 child_ops，
    命中按项装配违规并携带项编号。清单内容完全由画像概念决定，
    算子本身不感知任何业务。
    """

    op_code: ClassVar[str] = "list_for_each"
    name: ClassVar[str] = "清单逐条核查"
    description: ClassVar[str] = (
        "适用于文档中逐条记录的清单（如物品清单、人员名单、记录明细等）。"
        "系统会逐条取出清单中的每条记录，对每条分别执行配置的检查要求；"
        "某一条不符合时，生成一条对应的违规结果，并标注该条目的序号。"
    )
    applicable_data_kind: ClassVar[list[str]] = ["item_list"]
    result_semantics: ClassVar[str] = "hit_is_violation"
    params_model: ClassVar[type[BaseModel]] = ListForEachParams
