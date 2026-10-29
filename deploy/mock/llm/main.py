# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""通用 OpenAI-compatible LLM mock：仅返回空违规和固定置信度。"""

from __future__ import annotations

import json

from fastapi import FastAPI, Request

app = FastAPI(title="Document Review LLM Mock")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "mock-llm"}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> dict:
    """返回结构化 JSON 字符串；mock 只表示链路可用，不表达任何业务判断。"""
    payload = await request.json()
    text = json.dumps(
        {
            "thought": "通用 mock 审查完成",
            "tool_calls": [],
            "final": {
                "violations": [],
                "confidence": 0.5,
                "reasoning": "mock response",
            },
        },
        ensure_ascii=False,
    )
    return {
        "id": "chatcmpl-document-review-mock",
        "object": "chat.completion",
        "created": 0,
        "model": payload.get("model", "mock"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }
