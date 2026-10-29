# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""调用方定义任务的通用审核契约，不包含业务报告类型。"""

from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, field_validator


class EvaluationRequest(BaseModel):
    """原 PDF 的解析上下文、自然语言任务和结果 Schema。"""

    model_config = ConfigDict(extra="forbid")
    instruction: str = Field(min_length=1, max_length=50000)
    output_schema: dict[str, Any]
    markdown: str = Field(default="", max_length=2000000)
    content_list: list[dict[str, Any]] = Field(default_factory=list, max_length=50000)
    tools: list[str] = Field(
        default_factory=lambda: [
            "get_document_info",
            "read_pages",
            "search_text",
            "get_images",
            "inspect_page",
            "inspect_image",
        ]
    )
    max_tool_calls: int = Field(default=64, ge=1, le=256)
    max_output_tokens: int = Field(default=12000, ge=256, le=32000)
    require_visual_coverage: bool = True
    require_evidence: bool = True

    @field_validator("output_schema")
    @classmethod
    def local_schema_only(cls, value: dict[str, Any]) -> dict[str, Any]:
        """禁止 Schema 验证器根据调用方引用访问外部网络。"""

        def visit(node):
            if isinstance(node, dict):
                for key, child in node.items():
                    if key in {"$ref", "$dynamicRef", "$recursiveRef"} and (
                        not isinstance(child, str) or not child.startswith("#")
                    ):
                        raise ValueError("只允许 Schema 内部引用")
                    if key == "$id":
                        raise ValueError("不允许 Schema 重定义引用基址")
                    visit(child)
            elif isinstance(node, list):
                for child in node:
                    visit(child)

        visit(value)
        try:
            Draft202012Validator.check_schema(value)
        except Exception as exc:
            raise ValueError("output_schema 非法") from exc
        return value


class EvaluationResponse(BaseModel):
    """成功执行与需复核分离；业务结论由调用方确定性汇总。"""

    status: Literal["success", "needs_review"]
    data: dict[str, Any] | None = None
    page_count: int = 0
    error: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
