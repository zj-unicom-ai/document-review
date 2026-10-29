# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""PyMuPDF 侧栏批注输出。"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import pymupdf

SIDEBAR_WIDTH = 260


class AnnotationError(RuntimeError):
    """批注 PDF 生成失败。"""


def annotate_pdf(source_path: Path, output_path: Path, violations: list[dict[str, Any]]) -> Path:
    """在原 PDF 右侧追加批注栏；违规 page_idx 使用 0 基。"""
    try:
        if not source_path.is_file():
            raise FileNotFoundError(f"源 PDF 不存在: {source_path}")
        if source_path.resolve() == output_path.resolve():
            raise ValueError("批注输出不能覆盖源文件")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for violation in violations:
            grouped[int(violation.get("page_idx", 0))].append(violation)

        with pymupdf.open(source_path) as pdf:
            for page_idx, page in enumerate(pdf):
                original_width = page.rect.width
                new_rect = pymupdf.Rect(0, 0, original_width + SIDEBAR_WIDTH, page.rect.height)
                page.set_mediabox(new_rect)
                sidebar = pymupdf.Rect(original_width + 2, 2, new_rect.x1 - 2, new_rect.y1 - 2)
                page.draw_rect(sidebar, color=None, fill=(0.97, 0.97, 0.97))
                cursor_y = 28
                for number, violation in enumerate(grouped.get(page_idx, []), start=1):
                    severity = str(violation.get("severity", "一般"))
                    lines = [
                        f"{number:02d} [{severity}] {violation.get('rule_name', '')}",
                        str(violation.get("title", "")),
                        *textwrap_width(str(violation.get("content", "")), 22),
                    ]
                    for line in lines:
                        if cursor_y > new_rect.y1 - 16:
                            break
                        page.insert_text(
                            (original_width + 12, cursor_y),
                            line,
                            fontsize=9,
                            fontname="china-s",
                            color=(0.1, 0.1, 0.1),
                        )
                        cursor_y += 16
                    cursor_y += 8
            pdf.save(output_path)
        return output_path
    except Exception as exc:
        raise AnnotationError(f"生成批注 PDF 失败: {exc}") from exc


def textwrap_width(text: str, width: int) -> list[str]:
    """按显示宽度粗分中文文本；足够侧栏可读且不引入额外依赖。"""
    return [text[start : start + width] for start in range(0, len(text), width)] or [""]
