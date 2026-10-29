# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""无状态文档任务编排，复用通用规则引擎与受控文档工具。"""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pymupdf

from document_review.engine.document import DocumentContext, ParsedDocument
from document_review.engine.llm_rule import run_llm_rule
from document_review.engine.state import RulePlanItem
from document_review.engine.tools import validate_tool_whitelist
from document_review.integrations.llm import LlmService
from document_review.schemas.evaluation import EvaluationRequest, EvaluationResponse


class EvaluationService:
    """接收上传 bytes 和任务；返回结构化结果，退出时清理全部临时文件。"""

    def __init__(
        self,
        llm: LlmService | None,
        *,
        runner=run_llm_rule,
        timeout_s=600,
        max_pages=100,
        max_upload_mb=50,
    ):
        if timeout_s <= 0 or max_pages < 1 or max_upload_mb <= 0:
            raise ValueError("审核限制必须大于 0")
        self.max_upload_bytes = int(max_upload_mb * 1024 * 1024)
        self.llm = llm
        self.runner = runner
        self.timeout_s = timeout_s
        self.max_pages = max_pages

    async def evaluate(self, pdf_bytes: bytes, request: EvaluationRequest) -> EvaluationResponse:
        """隔离处理本次 PDF 与任务；输入错误抛 ValueError，取证失败返回需复核。"""
        if len(pdf_bytes) > self.max_upload_bytes:
            raise ValueError("PDF 超过大小限制")
        validate_tool_whitelist(request.tools)
        with TemporaryDirectory(prefix="document-evaluation-") as folder:
            path = Path(folder) / "source.pdf"
            path.write_bytes(pdf_bytes)
            try:
                with pymupdf.open(path) as pdf:
                    if not pdf.is_pdf or pdf.needs_pass or not 0 < len(pdf) <= self.max_pages:
                        raise ValueError("PDF 加密、为空或超过页数限制")
                    page_count = len(pdf)
                    blocks = request.content_list or [
                        {"type": "text", "text": page.get_text(), "page_idx": index}
                        for index, page in enumerate(pdf)
                    ]
                    images = []
                    for index, page in enumerate(pdf):
                        for info in page.get_image_info(xrefs=True):
                            if info["xref"] > 0:
                                box = pymupdf.Rect(info["bbox"]) * page.rotation_matrix
                                images.append(
                                    {
                                        "page_idx": index,
                                        "xref": info["xref"],
                                        "bbox_permille": [
                                            box.x0 / page.rect.width * 1000,
                                            box.y0 / page.rect.height * 1000,
                                            box.x1 / page.rect.width * 1000,
                                            box.y1 / page.rect.height * 1000,
                                        ],
                                    }
                                )
            except (RuntimeError, pymupdf.FileDataError) as exc:
                raise ValueError("无法读取 PDF") from exc
            for block in blocks:
                page_idx = block.get("page_idx", 0)
                if (
                    isinstance(page_idx, bool)
                    or not isinstance(page_idx, int)
                    or not 0 <= page_idx < page_count
                ):
                    raise ValueError("content_list 页码超出原 PDF")
            markdown = request.markdown or "\n".join(
                str(b.get("text") or b.get("table_body") or "") for b in blocks
            )
            doc = DocumentContext(ParsedDocument(markdown, blocks, {}, path, page_count, images))
            plan = RulePlanItem(
                plan_item_id="evaluation",
                rule_id=0,
                rule_code="evaluation",
                rule_name="文档任务",
                rule_type="llm",
                definition={
                    "instruction": request.instruction,
                    "output_schema": request.output_schema,
                    "tools": request.tools,
                    "budget": {
                        "max_tool_calls": request.max_tool_calls,
                        "max_output_tokens": request.max_output_tokens,
                    },
                    "require_visual_coverage": request.require_visual_coverage,
                    "require_evidence": request.require_evidence,
                },
                binding=None,
                classify_id=None,
                severity_default="一般",
                blocking_policy="advise",
                on_error_policy="fail_run",
                output_mode="extracted",
            )
            try:
                async with asyncio.timeout(self.timeout_s):
                    result = await self.runner(plan, doc, self.llm)
            except TimeoutError:
                return EvaluationResponse(
                    status="needs_review", page_count=page_count, error="审核超时，需复核"
                )
            if result.status != "success" or result.extracted is None:
                return EvaluationResponse(
                    status="needs_review",
                    page_count=page_count,
                    error="文档任务未完成，需复核",
                    tool_calls=result.tool_calls or [],
                )
            return EvaluationResponse(
                status="success",
                data=result.extracted,
                page_count=page_count,
                tool_calls=result.tool_calls or [],
            )
