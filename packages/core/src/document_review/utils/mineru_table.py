# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""MinerU ``table_body`` HTML 解析统一入口。

本模块是仓库内解析 MinerU ``table_body`` / ``html`` 表格片段的唯一归属；
新代码不要再自写 ``<tr>/<td>`` 正则或 HTMLParser 子类。数据形态约定见
``docs/mineru_content_list.md``。

两条解析路线并存，语义各有归属，迁移时不要互换：

- HTMLParser 路线（``TableTextParser`` / ``parse_table_rows``）：容忍嵌套
  标签，输出归一化文本单元格；``capture_img_src=True`` 时把单元格内
  ``<img>`` 的 ``src``/``data-src`` 也作为单元格内容捕获（隐患抽取的图片
  归属依赖此行为）。
- 正则路线（``table_row_htmls`` / ``row_cell_htmls`` 等）：机械拆行/拆格，
  供需要原始行/格 HTML（行内数图、跨页表重组）的调用方使用；只保证对
  MinerU 产出的规整 HTML 与历史正则行为一致。

尚未迁移到本模块的解析点（触碰对应代码时再迁）：

- ``app/service/picture_similar_service.py::_iter_content_image_refs``
- 兼容历史解析产物的表格行抽取。
"""

import re
from html.parser import HTMLParser

_ROW_WITH_TR_RE = re.compile(r"<tr\b[^>]*>.*?</tr>", re.I | re.S)
_ROW_INNER_RE = re.compile(r"<tr\b[^>]*>(.*?)</tr>", re.I | re.S)
_CELL_RE = re.compile(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
# strict：要求 src 是 <img 后的第一个属性（process_record / sign_in 的历史语义）。
_IMG_SRC_STRICT_RE = re.compile(r"<img\s+src=[\"']([^\"']+)[\"']", re.I)
# flexible：src 可出现在任意属性位置（hangz_plan_four_color 的历史语义）。
_IMG_SRC_FLEXIBLE_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)


def _normalize_text(text) -> str:
    """压缩空白并去首尾，避免 OCR 换行影响规则匹配。"""
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


class TableTextParser(HTMLParser):
    """把 MinerU 返回的 HTML table 解析成行和归一化文本单元格。

    ``capture_img_src=True`` 时，单元格内 ``<img>`` 的 ``src`` 或
    ``data-src`` 属性值也作为单元格内容捕获。
    """

    def __init__(self, capture_img_src: bool = False):
        super().__init__()
        self.capture_img_src = capture_img_src
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._current_cell = []
        elif tag == "img" and self.capture_img_src and self._current_cell is not None:
            attrs_dict = dict(attrs)
            src = attrs_dict.get("src") or attrs_dict.get("data-src") or ""
            if src:
                self._current_cell.append(src)

    def handle_data(self, data: str):
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str):
        if tag in ("td", "th") and self._current_cell is not None:
            text = _normalize_text("".join(self._current_cell))
            if self._current_row is not None:
                self._current_row.append(text)
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            self.rows.append(self._current_row)
            self._current_row = None


def parse_table_rows(html: str, *, capture_img_src: bool = False) -> list[list[str]]:
    """HTMLParser 路线：解析为 行 × 归一化文本单元格。"""
    parser = TableTextParser(capture_img_src=capture_img_src)
    parser.feed(html or "")
    return parser.rows


def table_row_htmls(html: str, *, keep_tr: bool = True) -> list[str]:
    """正则路线拆行。

    ``keep_tr=True`` 返回带 ``<tr>`` 标签的整行 HTML（供跨页表重组）；
    ``keep_tr=False`` 返回行内 HTML（供在行内继续找 ``<img>`` 等）。
    """
    pattern = _ROW_WITH_TR_RE if keep_tr else _ROW_INNER_RE
    return pattern.findall(html or "")


def row_cell_htmls(row_html: str) -> list[str]:
    """取一行内各单元格的原始内部 HTML。"""
    return _CELL_RE.findall(row_html or "")


def row_cell_texts(row_html: str) -> list[str]:
    """取一行内各单元格的去标签文本（仅去首尾空白，不压缩内部空白）。

    需要更强归一化（如删除全部空白）的调用方，应在自己一侧基于
    ``row_cell_htmls`` + ``strip_html_tags`` 自行处理。
    """
    return [strip_html_tags(cell).strip() for cell in row_cell_htmls(row_html)]


def strip_html_tags(fragment: str) -> str:
    return _TAG_RE.sub("", fragment or "")


def extract_img_srcs(fragment: str, *, mode: str = "strict") -> list[str]:
    """提取 HTML 片段中 ``<img>`` 的 src 属性值列表。

    - ``mode="strict"``：src 必须是 ``<img`` 后的第一个属性；
    - ``mode="flexible"``：src 可在任意属性位置。

    两种模式对应不同规则的历史行为，迁移时保持原调用点语义，不要混用。
    """
    if mode == "strict":
        pattern = _IMG_SRC_STRICT_RE
    elif mode == "flexible":
        pattern = _IMG_SRC_FLEXIBLE_RE
    else:
        raise ValueError(f"未知的 img 提取模式: {mode}")
    return pattern.findall(fragment or "")
