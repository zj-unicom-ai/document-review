# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""MinerU content_list bbox（0–1000 千分比）与 PyMuPDF pt 坐标换算。

MinerU content_list 的 bbox 按页面宽、高各自归一化到 0–1000 的千分比
整数（原点左上、y 向下、int 截断），pipeline/vlm/hybrid 三后端一致，
2.2.0 引入后 3.x 全系公式未变。换算基准是 PyMuPDF 的 page.rect
（旋转后显示空间的 pt 尺寸），不要用 mediabox。
详见 docs/mineru_content_list.md 坐标约定一节。
"""

from __future__ import annotations

from typing import Any

MINERU_BBOX_SCALE = 1000.0

# MinerU 归一化 int 截断（≤1‰ 页宽高）+ page_size 截 int + VLM 输出量化
# 三层误差叠加，千分比空间比较容差取 3‰（A4 高约 2.5pt）。
PERMILLE_TOLERANCE = 3.0

_BBoxTuple = tuple[float, float, float, float]


def _coerce_bbox(bbox: Any) -> _BBoxTuple | None:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        return tuple(float(v) for v in bbox)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def pt_bbox_to_permille(
    bbox: Any,
    page_width_pt: float,
    page_height_pt: float,
) -> _BBoxTuple | None:
    """pt bbox 换算到 MinerU 千分比空间；bbox 或页尺寸非法时返回 None。"""
    values = _coerce_bbox(bbox)
    if values is None or page_width_pt <= 0 or page_height_pt <= 0:
        return None
    x0, y0, x1, y1 = values
    return (
        x0 * MINERU_BBOX_SCALE / page_width_pt,
        y0 * MINERU_BBOX_SCALE / page_height_pt,
        x1 * MINERU_BBOX_SCALE / page_width_pt,
        y1 * MINERU_BBOX_SCALE / page_height_pt,
    )


def permille_bbox_to_pt(
    bbox: Any,
    page_width_pt: float,
    page_height_pt: float,
) -> _BBoxTuple | None:
    """MinerU 千分比 bbox 换算到 pt；bbox 或页尺寸非法时返回 None。"""
    values = _coerce_bbox(bbox)
    if values is None or page_width_pt <= 0 or page_height_pt <= 0:
        return None
    x0, y0, x1, y1 = values
    return (
        x0 * page_width_pt / MINERU_BBOX_SCALE,
        y0 * page_height_pt / MINERU_BBOX_SCALE,
        x1 * page_width_pt / MINERU_BBOX_SCALE,
        y1 * page_height_pt / MINERU_BBOX_SCALE,
    )
