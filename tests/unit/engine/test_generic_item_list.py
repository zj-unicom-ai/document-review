# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-120 通用 item_list 契约测试。"""

from __future__ import annotations

from pathlib import Path

from document_review.engine.document import DocumentContext, ParsedDocument
from document_review.schemas.profile import ConceptBinding


def _table(html: str, page_idx: int = 0) -> dict:
    return {"type": "table", "table_body": f"<table>{html}</table>", "page_idx": page_idx}


def _document(*tables: dict) -> DocumentContext:
    return DocumentContext(
        ParsedDocument(
            markdown="",
            blocks=list(tables),
            layout={},
            pdf_path=Path(__file__),
            page_count=1,
        )
    )


def _binding(**locator: object) -> ConceptBinding:
    return ConceptBinding(
        concept_code="records",
        status="bound",
        targets=[{"kind": "item_list", "locator": locator, "page_idx": 0}],
    )


def test_bl120_a1_horizontal_table_rows_become_generic_items() -> None:
    doc = _document(
        _table(
            "<tr><th>编号</th><th>名称</th><th>状态</th></tr>"
            "<tr><td>A1</td><td>第一条</td><td>有效</td></tr>"
            "<tr><td>A2</td><td>第二条</td><td>待复核</td></tr>"
        )
    )

    items = doc.get_list_items(_binding())

    assert [item["no"] for item in items] == ["A1", "A2"]
    assert items[0]["名称"] == "第一条"
    assert items[0]["description"] == "A1 / 第一条 / 有效"
    assert items[1]["状态"] == "待复核"


def test_bl120_a2_vertical_key_value_table_becomes_one_item() -> None:
    doc = _document(
        _table(
            "<tr><td>名称</td><td>通用记录</td></tr>"
            "<tr><td>负责人</td><td>张三</td></tr>"
            "<tr><td>状态</td><td>有效</td></tr>"
        )
    )

    items = doc.get_list_items(_binding(list_layout="vertical"))

    assert len(items) == 1
    assert items[0]["名称"] == "通用记录"
    assert items[0]["负责人"] == "张三"
    assert "通用记录" in items[0]["description"]


def test_bl120_a1_operator_context_exposes_list_items() -> None:
    doc = _document(
        _table("<tr><th>编号</th><th>名称</th></tr><tr><td>A1</td><td>第一条</td></tr>")
    )

    context = doc.to_operator_context(_binding())

    assert [item["no"] for item in context.list_items] == ["A1"]


def test_bl120_e3_public_production_code_has_no_legacy_item_terms() -> None:
    """公开生产代码不得保留旧行业命名或地市解析词。"""
    roots = (Path("app"), Path("packages/core/src"), Path("web/src"))
    legacy_terms = (
        "\u0068azard_list",
        "get_\u0068azards",
        "\u0068azards",
        "\u0068azard_no",
    )
    city_terms = (
        "\u6e29\u5dde",
        "\u676d\u5dde",
        "\u8862\u5dde",
    )
    hits: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or path.name.endswith((".test.ts", ".test.tsx"))
                or path == Path("app/seed/sample_rules.py")
                or path.suffix not in {".py", ".ts", ".tsx"}
            ):
                continue
            text = path.read_text(encoding="utf-8")
            if any(term in text for term in legacy_terms + city_terms):
                hits.append(path.as_posix())

    assert not hits
