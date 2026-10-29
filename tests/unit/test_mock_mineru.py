# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-007 MinerU mock 契约测试。"""

from __future__ import annotations

import io

import pymupdf
from fastapi.testclient import TestClient

from deploy.mock.mineru.main import app


def _pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "# 通用文档说明", fontname="china-s")
    content = doc.tobytes()
    doc.close()
    return content


def test_bl007_a3_mock_mineru_accepts_platform_files_field() -> None:
    """平台 MinerU 客户端使用 files 字段上传，mock 必须接受同一契约。"""
    client = TestClient(app)

    response = client.post(
        "/file_parse",
        data={"return_md": "true"},
        files={"files": ("generic.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["file_names"] == ["generic.pdf"]
    result = body["results"]["generic.pdf"]
    assert "通用文档说明" in result["md_content"]
