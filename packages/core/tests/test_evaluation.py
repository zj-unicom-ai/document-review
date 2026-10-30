# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-018：安装后的核心接口不依赖 Web 或数据库。"""

import asyncio
import sys

import pymupdf


def test_a1_core_evaluates_without_host_app():
    loaded = set(sys.modules)
    from document_review import EvaluationRequest, EvaluationService
    from document_review.engine.llm_rule import AgentStep, ToolCallRequest
    from document_review.integrations.llm import LlmService, StructuredResponse

    class Provider:
        requested = False

        async def structured(self, schema, messages, **kwargs):
            if not self.requested:
                self.requested = True
                data = AgentStep(
                    tool_calls=[
                        ToolCallRequest(
                            name="read_pages", args={"start_page_idx": 0, "end_page_idx": 0}
                        )
                    ]
                )
            else:
                data = AgentStep(
                    final={"answer": "原文已读取", "evidence": [{"page_idx": 0, "quote": "source"}]}
                )
            return StructuredResponse(parsed=data, raw={}, usage={})

    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "source")
        content = pdf.tobytes()
    result = asyncio.run(
        EvaluationService(LlmService(Provider())).evaluate(
            content,
            EvaluationRequest(
                instruction="读取原文",
                output_schema={"type": "object"},
                require_visual_coverage=False,
            ),
        )
    )
    assert result.status == "success"
    assert result.data["answer"] == "原文已读取"
    assert not any(
        name == "app" or name.startswith(("app.", "sqlalchemy", "fastapi"))
        for name in set(sys.modules) - loaded
    )


def test_e1_core_rejects_oversize_and_unknown_tools_before_model():
    import pytest
    from document_review import EvaluationRequest, EvaluationService

    with pymupdf.open() as pdf:
        pdf.new_page()
        content = pdf.tobytes()
    task = EvaluationRequest(instruction="test", output_schema={})
    with pytest.raises(ValueError, match="大小"):
        asyncio.run(EvaluationService(None, max_upload_mb=0.00001).evaluate(content, task))
    with pytest.raises(ValueError):
        asyncio.run(
            EvaluationService(None).evaluate(
                content, task.model_copy(update={"tools": ["read_server_file"]})
            )
        )


def test_e2_missing_model_is_needs_review():
    from document_review import EvaluationRequest, EvaluationService

    with pymupdf.open() as pdf:
        pdf.new_page()
        content = pdf.tobytes()
    result = asyncio.run(
        EvaluationService(None).evaluate(
            content, EvaluationRequest(instruction="test", output_schema={})
        )
    )
    assert result.status == "needs_review"
    assert result.data is None
