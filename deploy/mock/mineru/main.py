# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""通用 MinerU mock：用 PyMuPDF 生成标准 artifact bundle，不包含行业结论。"""

from __future__ import annotations

import json

import pymupdf
from fastapi import FastAPI, File, UploadFile

app = FastAPI(title="Document Review MinerU Mock")


@app.get("/health")
async def health() -> dict:
    """容器健康探针。"""
    return {"status": "ok", "service": "mock-mineru"}


@app.post("/file_parse")
async def file_parse(files: UploadFile = File(...)) -> dict:
    """按现有 self-host `/file_parse` 契约返回通用文本解析结果。"""
    payload = await files.read()
    content_list: list[dict] = []
    markdown_lines: list[str] = []
    with pymupdf.open(stream=payload, filetype="pdf") as pdf:
        for page_idx, page in enumerate(pdf):
            text = page.get_text("text").strip()
            markdown_lines.append(f"<!-- page {page_idx} -->\n{text}\n")
            if text:
                content_list.append(
                    {
                        "type": "text",
                        "text": text,
                        "page_idx": page_idx,
                    }
                )
    if not markdown_lines:
        markdown_lines.append("")

    name = files.filename or "document.pdf"
    result = {
        "md_content": "\n".join(markdown_lines),
        "content_list": json.dumps(content_list, ensure_ascii=False),
        "middle_json": {"page_count": len(content_list)},
        "images": {},
    }
    return {"file_names": [name], "results": {name: result}}
