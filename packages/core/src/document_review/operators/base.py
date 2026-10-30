# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""算子基类与执行上下文契约。

算子是规则的最小执行单元。规则由一个或多个算子按 ops 链组成。算子只返回
"业务命中"（`OpResult`），违规字段（severity / classify_id / mark_text / meta）
由引擎按规则主表与 `ops[*].fail` 模板统一装配（设计 §6.2 红线）。

P1 阶段：定义 `OperatorContext` 契约与算子实现；真实 `DocumentContext`
由 P2 实现，按本契约提供数据。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal

from pydantic import BaseModel

ResultSemantics = Literal["hit_is_violation", "hit_is_pass"]


@dataclass
class OpResult:
    """算子单次执行的命中结果。多个命中由引擎合并为违规项。

    - `hit` 表示算子"命中"——具体语义由算子的 `result_semantics` 决定：
      `hit_is_violation`（默认）下 hit=True 即违规；`hit_is_pass` 下 hit=True 即通过。
    - `extra` 携带命中的上下文数据（如缺哪些字段、命中哪些行），合并入违规 meta.extra。
    - `item_no` 仅在列表逐项算子（list_for_each）的子检查中使用，语义为“清单项编号”。
    """

    hit: bool
    extra: dict[str, Any] = field(default_factory=dict)
    item_no: str | None = None


@dataclass
class OperatorContext:
    """算子执行上下文契约。

    DocumentContext（P2）按此契约构造 ctx 并喂给算子。本期单测用
    `dataclasses.replace` 或裸构造。

    字段语义：
    - `fields`：键为 alias（按算子 params.field_aliases 匹配），值为字符串。
    - `sections`：报告章节列表，元素 `{title, ordinal, page_idx, content}`。
    - `table_rows`：当前概念对应的表格行，每行 `{列名: 值}`。
    - `table_columns`：表头列名顺序。
    - `images`：图片列表，元素 `{page_idx, section_title, kind, ocr_text?, bytes_b64?, bbox?, ...}`。
    - `list_items`：结构化条目数组，由绑定表格的表头 / 键值行转换得到。
    - `markdown_text`：全文 markdown，供 LLM 理解类算子组装受控上下文。
    """

    fields: dict[str, str] = field(default_factory=dict)
    # 检查对象（锚点绑定目标）所在页，0 基；供 LLM 算子输出违规页码
    anchor_page_idx: int | None = None
    # 锚点表格所在页，0 基；表格跨页时取首表页码
    table_page_idx: int | None = None
    sections: list[dict[str, Any]] = field(default_factory=list)
    table_rows: list[dict[str, Any]] = field(default_factory=list)
    table_columns: list[str] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)
    list_items: list[dict[str, Any]] = field(default_factory=list)
    markdown_text: str = ""
    # 多证据规则按名称携带的受控证据摘要，供 LLM 理解类算子对比多组内容。
    evidence: dict[str, Any] = field(default_factory=dict)
    # LLM 服务与图片字节提取由引擎注入；算子不得自行创建模型客户端。
    llm: Any | None = None
    get_image_bytes: Callable[[dict[str, Any]], bytes] | None = None


class OperatorBase:
    """算子基类。子类设置下列类属性并实现 `execute`。"""

    op_code: ClassVar[str] = ""
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""
    applicable_data_kind: ClassVar[list[str]] = []
    params_model: ClassVar[type[BaseModel]] = BaseModel
    result_semantics: ClassVar[ResultSemantics] = "hit_is_violation"
    model_profile: ClassVar[str | None] = None  # 仅 LLM 类算子使用

    def execute(  # pragma: no cover
        self, ctx: OperatorContext, params: BaseModel
    ) -> OpResult | Awaitable[OpResult]:
        raise NotImplementedError(f"{self.op_code} 尚未实现")
