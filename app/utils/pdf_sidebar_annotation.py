# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""生成“原 PDF 页 + 右侧按页批注栏”的宽版 PDF。

本模块只负责渲染，不做规则审核，也不做表格内 bbox 精确定位。
审核结果应直接携带 page_idx，侧边栏只按页展示问题。
"""

from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

ALLOWED_SEVERITIES = {"提醒", "一般", "严重"}

# mark_text 在正文上的高亮配色：偏淡红半透明底 + 深红描边，比黄底更醒目、且不遮挡原文。
MARK_HIGHLIGHT_FILL = (1, 0.75, 0.75)
MARK_HIGHLIGHT_BORDER = (0.7, 0.18, 0.18)
MARK_HIGHLIGHT_FILL_OPACITY = 0.32
MARK_HIGHLIGHT_STROKE_OPACITY = 0.7
MARK_HIGHLIGHT_BORDER_WIDTH = 0.6
# 命中文本不在任何识别出的表格单元格时，沿用文本 bbox 并外扩此 padding。
MARK_HIGHLIGHT_FALLBACK_PADDING = 1.5

# Noto CJK 的 TTC 可能被 PyMuPDF 选到 JP 子字体，侧边栏优先使用简体中文环境更稳定的文泉驿。
DEFAULT_REGULAR_FONT_PATHS = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
]
DEFAULT_BOLD_FONT_PATHS = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf",
]


@dataclass(frozen=True)
class SidebarAnnotationOptions:
    """侧边栏批注的渲染参数。"""

    sidebar_width: int = 250
    top_margin: int = 40
    max_note_chars: int = 200
    show_clean_page_box: bool = False


@dataclass(frozen=True)
class SidebarInsertResult:
    """单次侧边栏插入结果。"""

    rendered_count: int
    remaining_prefix: tuple[dict[str, Any], ...] = ()


def normalize_sidebar_annotations(
    annotations: list[dict[str, Any]],
    page_count: int,
    max_note_chars: int,
) -> list[dict[str, Any]]:
    """清洗审核批注数据，过滤无效页码并统一字段和严重程度。"""

    normalized = []
    for item in annotations or []:
        page_idx = _safe_int(item.get("page_idx"))
        if page_idx is None or page_idx < 0 or page_idx >= page_count:
            continue

        raw_content = str(item.get("content") or "").strip()
        if not raw_content:
            # 兼容旧审核结果结构，新接口优先传 content。
            raw_content = _merge_legacy_content(item)
        if not raw_content:
            continue

        summary_content = str(item.get("summary_content") or "").strip()
        sidebar_content = summary_content or raw_content
        meta = item.get("meta")
        skip_detail = isinstance(meta, dict) and bool(meta.get("skip_detail"))
        detail_content = "" if skip_detail else str(item.get("detail_content") or "").strip()
        if summary_content and not detail_content and not skip_detail:
            detail_content = raw_content

        severity = str(item.get("severity") or "一般").strip()
        if severity not in ALLOWED_SEVERITIES:
            severity = "一般"

        title = str(
            item.get("title") or item.get("rule") or item.get("offending_text") or "审核问题"
        ).strip()
        normalized_item = {
            "page_idx": page_idx,
            "severity": severity,
            "title": title,
            # summary_content 是业务规则专门给侧边栏准备的精炼文案，交给分页逻辑处理；
            # 只有没有摘要的原始 content 才按通用长度截断。
            "content": sidebar_content
            if summary_content
            else _truncate_text(sidebar_content, max_note_chars),
        }
        if detail_content:
            normalized_item["detail_content"] = detail_content
        if isinstance(meta, dict):
            normalized_item["meta"] = meta
        mark_texts = _normalize_mark_texts(item.get("mark_text"))
        if mark_texts:
            # 留作正文高亮使用；不参与侧边栏文案。
            normalized_item["mark_text"] = mark_texts
        normalized.append(normalized_item)
    return normalized


def generate_sidebar_annotated_pdf(
    pdf_bytes: bytes,
    annotations: list[dict[str, Any]],
    options: SidebarAnnotationOptions | None = None,
) -> bytes:
    """生成左侧原页、右侧按页批注栏的宽版 PDF 字节流。"""

    options = options or SidebarAnnotationOptions()
    src = fitz.open(stream=pdf_bytes, filetype="pdf")
    normalized = normalize_sidebar_annotations(
        annotations,
        page_count=len(src),
        max_note_chars=max(1, options.max_note_chars),
    )
    by_page = _group_by_page(normalized)

    out = fitz.open()
    regular_font_path = _find_font_path(DEFAULT_REGULAR_FONT_PATHS)
    bold_font_path = _find_font_path(DEFAULT_BOLD_FONT_PATHS)
    font_archive = fitz.Archive(str(regular_font_path.parent)) if regular_font_path else None
    css = _build_sidebar_css(
        regular_font_path.name if regular_font_path else None,
        bold_font_path.name
        if bold_font_path
        and regular_font_path
        and bold_font_path.parent == regular_font_path.parent
        else None,
    )

    for page_no, src_page in enumerate(src):
        src_rect = src_page.rect
        new_page = out.new_page(
            width=src_rect.width + options.sidebar_width,
            height=src_rect.height,
        )
        # 左侧原页使用原始尺寸放置，只横向增加侧栏，不压缩原 PDF。
        new_page.show_pdf_page(fitz.Rect(0, 0, src_rect.width, src_rect.height), src, page_no)
        issues_on_page = by_page.get(page_no, [])
        # 在原文上将每条批注的 mark_text 命中位置（优先整格）描出高亮，方便用户定位。
        _apply_mark_text_highlights(src_page, new_page, issues_on_page)
        remaining_issues = _render_sidebar(
            new_page,
            original_width=src_rect.width,
            issues=issues_on_page,
            page_no=page_no,
            total_pages=len(src),
            options=options,
            css=css,
            font_archive=font_archive,
        )
        continuation_no = 1
        while remaining_issues:
            continuation_page = _new_sidebar_continuation_page(
                out,
                width=src_rect.width + options.sidebar_width,
                height=src_rect.height,
                original_width=src_rect.width,
            )
            remaining_issues = _render_sidebar(
                continuation_page,
                original_width=src_rect.width,
                issues=remaining_issues,
                page_no=page_no,
                total_pages=len(src),
                options=options,
                css=css,
                font_archive=font_archive,
                continuation_no=continuation_no,
            )
            continuation_no += 1

    output = out.tobytes(deflate=True, garbage=4)
    out.close()
    src.close()
    return output


def _render_sidebar(
    page: fitz.Page,
    *,
    original_width: float,
    issues: list[dict[str, Any]],
    page_no: int,
    total_pages: int,
    options: SidebarAnnotationOptions,
    css: str,
    font_archive: fitz.Archive | None,
    continuation_no: int = 0,
) -> list[dict[str, Any]]:
    sidebar = fitz.Rect(original_width, 0, page.rect.width, page.rect.height)
    page.draw_rect(sidebar, color=(0.78, 0.78, 0.78), fill=(0.985, 0.985, 0.975), width=0.8)
    page.draw_line(
        (original_width, 0), (original_width, page.rect.height), color=(0.55, 0.55, 0.55), width=1
    )

    margin = 16
    content_rect = fitz.Rect(
        sidebar.x0 + margin,
        options.top_margin,
        sidebar.x1 - margin,
        page.rect.height - 38,
    )
    insert_result = _insert_sidebar_html(
        page,
        content_rect,
        issues,
        page_no,
        options,
        css,
        font_archive,
        continuation_no=continuation_no,
    )
    _insert_footer(page, sidebar, page_no, total_pages, font_archive is not None)
    if insert_result.rendered_count <= 0 and not insert_result.remaining_prefix:
        return []
    return list(insert_result.remaining_prefix) + issues[insert_result.rendered_count :]


def _new_sidebar_continuation_page(
    doc: fitz.Document,
    *,
    width: float,
    height: float,
    original_width: float,
) -> fitz.Page:
    page = doc.new_page(width=width, height=height)
    original_area = fitz.Rect(0, 0, original_width, height)
    page.draw_rect(original_area, color=None, fill=(1, 1, 1), width=0)
    page.draw_line((original_width, 0), (original_width, height), color=(0.55, 0.55, 0.55), width=1)
    return page


def _insert_sidebar_html(
    page: fitz.Page,
    rect: fitz.Rect,
    issues: list[dict[str, Any]],
    page_no: int,
    options: SidebarAnnotationOptions,
    css: str,
    font_archive: fitz.Archive | None,
    continuation_no: int = 0,
) -> SidebarInsertResult:
    sidebar_html = _build_sidebar_html(issues, page_no, options, continuation_no=continuation_no)
    if _sidebar_chunk_fits_rect(rect, sidebar_html, issues, css, font_archive):
        page.insert_htmlbox(
            rect,
            sidebar_html,
            css=css,
            archive=font_archive,
            scale_low=0.72,
            # 中文没有空格分词，默认 word width 缩放可能把行尾汉字挤窄。
            _scale_word_width=False,
        )
        return SidebarInsertResult(rendered_count=len(issues))

    visible_count = _find_visible_count(
        rect, issues, page_no, options, css, font_archive, continuation_no=continuation_no
    )
    if visible_count > 0:
        page.insert_htmlbox(
            rect,
            _build_sidebar_html(
                issues[:visible_count],
                page_no,
                options,
                continuation_no=continuation_no,
                total_issue_count=len(issues),
            ),
            css=css,
            archive=font_archive,
            scale_low=0.72,
            _scale_word_width=False,
        )
        return SidebarInsertResult(rendered_count=visible_count)

    split_issue = _split_first_sidebar_issue(
        rect,
        issues[0] if issues else {},
        page_no,
        options,
        css,
        font_archive,
        continuation_no=continuation_no,
        total_issue_count=len(issues),
    )
    if split_issue is not None:
        head_issue, tail_issue = split_issue
        page.insert_htmlbox(
            rect,
            _build_sidebar_html(
                [head_issue],
                page_no,
                options,
                continuation_no=continuation_no,
                total_issue_count=len(issues),
            ),
            css=css,
            archive=font_archive,
            scale_low=0.72,
            _scale_word_width=False,
        )
        return SidebarInsertResult(rendered_count=1, remaining_prefix=(tail_issue,))

    # 极小页面上连一条批注也放不下时，显示兜底提示，避免强行绘制导致越界。
    visible_count = _find_compact_visible_count(rect, issues, page_no, options, css, font_archive)
    visible = _compact_sidebar_issues(issues[:visible_count], options)
    hidden_count = max(0, len(issues) - len(visible))
    compact_html = _build_sidebar_html(
        visible,
        page_no,
        options,
        hidden_count=hidden_count,
        continuation_no=continuation_no,
    )
    page.insert_htmlbox(
        rect,
        compact_html,
        css=css,
        archive=font_archive,
        scale_low=0.65,
        # 同上，避免中文被横向压缩。
        _scale_word_width=False,
    )
    return SidebarInsertResult(rendered_count=visible_count)


def _find_visible_count(
    rect: fitz.Rect,
    issues: list[dict[str, Any]],
    page_no: int,
    options: SidebarAnnotationOptions,
    css: str,
    font_archive: fitz.Archive | None,
    *,
    continuation_no: int = 0,
) -> int:
    for visible_count in range(len(issues), 0, -1):
        html_text = _build_sidebar_html(
            issues[:visible_count],
            page_no,
            options,
            continuation_no=continuation_no,
            total_issue_count=len(issues),
        )
        if _sidebar_chunk_fits_rect(rect, html_text, issues[:visible_count], css, font_archive):
            return visible_count
    return 0


def _find_compact_visible_count(
    rect: fitz.Rect,
    issues: list[dict[str, Any]],
    page_no: int,
    options: SidebarAnnotationOptions,
    css: str,
    font_archive: fitz.Archive | None,
) -> int:
    """在摘要模式下估算侧栏最多可展示的批注数。"""

    for visible_count in range(len(issues), 0, -1):
        hidden_count = len(issues) - visible_count
        visible = _compact_sidebar_issues(issues[:visible_count], options)
        compact_html = _build_sidebar_html(
            visible,
            page_no,
            options,
            hidden_count=hidden_count,
        )
        if _sidebar_chunk_fits_rect(rect, compact_html, visible, css, font_archive, scale_low=0.65):
            return visible_count
    return 0


def _compact_sidebar_issues(
    issues: list[dict[str, Any]], options: SidebarAnnotationOptions
) -> list[dict[str, Any]]:
    compact_issues = []
    for issue in issues:
        compact_issue = dict(issue)
        compact_issue["content"] = _truncate_text(
            str(compact_issue.get("content") or ""),
            min(46, options.max_note_chars),
        )
        compact_issues.append(compact_issue)
    return compact_issues


def _split_first_sidebar_issue(
    rect: fitz.Rect,
    issue: dict[str, Any],
    page_no: int,
    options: SidebarAnnotationOptions,
    css: str,
    font_archive: fitz.Archive | None,
    *,
    continuation_no: int = 0,
    total_issue_count: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """将单条过长批注按正文切成当前页可展示的首段和剩余段。"""

    content = str(issue.get("content") or "").strip()
    split_points = _sidebar_split_points(content)
    if not split_points:
        return None

    best_prefix = ""
    best_tail = ""
    low = 0
    high = len(split_points) - 1
    while low <= high:
        mid = (low + high) // 2
        split_at = split_points[mid]
        prefix = content[:split_at].strip()
        tail = content[split_at:].strip()
        if not prefix or not tail:
            high = mid - 1
            continue

        head_issue = dict(issue)
        head_issue["content"] = prefix
        html_text = _build_sidebar_html(
            [head_issue],
            page_no,
            options,
            continuation_no=continuation_no,
            total_issue_count=total_issue_count,
        )
        if _sidebar_chunk_fits_rect(rect, html_text, [head_issue], css, font_archive):
            best_prefix = prefix
            best_tail = tail
            low = mid + 1
        else:
            high = mid - 1

    if not best_prefix or not best_tail:
        return None

    head_issue = dict(issue)
    head_issue["content"] = best_prefix
    tail_issue = dict(issue)
    tail_issue["title"] = _continued_title(str(issue.get("title") or "审核问题"))
    tail_issue["content"] = best_tail
    return head_issue, tail_issue


def _sidebar_split_points(text: str) -> list[int]:
    """生成侧栏正文拆分点，优先按行和句读，兜底按固定长度切分。"""

    content = str(text or "")
    if len(content.strip()) < 2:
        return []

    points: set[int] = set()
    break_chars = "\n。！？；;，、,.!? )）"
    for index, char in enumerate(content, start=1):
        if char in break_chars:
            points.add(index)
    for index in range(24, len(content), 24):
        points.add(index)
    return sorted(point for point in points if 8 <= point < len(content.strip()))


def _continued_title(title: str) -> str:
    if title.endswith("（续）"):
        return title
    return f"{title}（续）"


def _sidebar_chunk_fits_rect(
    rect: fitz.Rect,
    html_text: str,
    issues: list[dict[str, Any]],
    css: str,
    font_archive: fitz.Archive | None,
    *,
    scale_low: float = 0.72,
) -> bool:
    """试排侧栏 HTML，并确认本切片的每条批注关键文本确实渲染出来。"""

    doc = fitz.open()
    page = doc.new_page(width=rect.width, height=rect.height)
    spare_height, _scale = page.insert_htmlbox(
        fitz.Rect(0, 0, rect.width, rect.height),
        html_text,
        css=css,
        archive=font_archive,
        scale_low=scale_low,
        _scale_word_width=False,
    )
    rendered_text = _compact_rendered_text(page.get_text())
    doc.close()
    if spare_height < 0:
        return False
    return all(_issue_visible_in_text(issue, rendered_text) for issue in issues)


def _html_fits_rect(
    rect: fitz.Rect,
    html_text: str,
    css: str,
    font_archive: fitz.Archive | None,
) -> bool:
    """用临时页面试排 HTML，避免在真实页面上留下试排内容。"""

    doc = fitz.open()
    page = doc.new_page(width=rect.width, height=rect.height)
    spare_height, _scale = page.insert_htmlbox(
        fitz.Rect(0, 0, rect.width, rect.height),
        html_text,
        css=css,
        archive=font_archive,
        scale_low=0.65,
        _scale_word_width=False,
    )
    doc.close()
    # 留一点余量给不同页面坐标和页脚，避免“刚好能放下”时底部提示被裁掉。
    return spare_height >= 14


def _issue_visible_in_text(issue: dict[str, Any], rendered_text: str) -> bool:
    visibility_text = _visibility_compare_text(rendered_text)
    content_signatures = _extractable_signatures(str(issue.get("content") or ""))
    if content_signatures:
        return all(
            _visibility_compare_text(signature) in visibility_text
            for signature in content_signatures
        )
    if str(issue.get("content") or "").strip():
        return True
    title_signatures = _extractable_signatures(str(issue.get("title") or ""))
    return bool(
        title_signatures
        and all(
            _visibility_compare_text(signature) in visibility_text for signature in title_signatures
        )
    )


def _extractable_signatures(value: str) -> list[str]:
    # PyMuPDF 对部分 CJK 字体的文本回抽不稳定；只对 ASCII 标识做强校验。
    return [
        signature for signature in _render_signatures(value) if re.search(r"[A-Za-z]", signature)
    ]


def _render_signatures(value: str) -> list[str]:
    compact = _compact_rendered_text(value)
    if not compact:
        return []
    signature_len = min(24, len(compact))
    signatures = [compact[:signature_len]]
    if len(compact) > signature_len:
        middle_start = max(0, (len(compact) - signature_len) // 2)
        signatures.append(compact[middle_start : middle_start + signature_len])
        signatures.append(compact[-signature_len:])
    return unique_texts(signatures)


def _compact_rendered_text(value: str) -> str:
    return " ".join(str(value).replace("\xa0", " ").split())


def _visibility_compare_text(value: str) -> str:
    # PyMuPDF 回抽 insert_htmlbox 文本时会在中文换行处插入空格，
    # 例如 "PE线（" 可能变成 "PE线 （"；可见性校验只关心文本是否出现。
    # 部分 CJK 字体还会把常用汉字回抽成兼容字形，例如 "不" -> "不"、
    # "年" -> "年"；比较前统一做 NFKC，避免误判为未渲染而错误拆页。
    normalized = unicodedata.normalize("NFKC", _compact_rendered_text(value))
    return re.sub(r"\s+", "", normalized)


def _insert_footer(
    page: fitz.Page, sidebar: fitz.Rect, page_no: int, total_pages: int, has_cjk_font: bool
) -> None:
    rect = fitz.Rect(sidebar.x0 + 16, page.rect.height - 28, sidebar.x1 - 16, page.rect.height - 10)
    kwargs = {
        "fontsize": 7.5,
        "color": (0.55, 0.55, 0.55),
        "align": 1,
    }
    font_path = _find_font_path(DEFAULT_REGULAR_FONT_PATHS) if has_cjk_font else None
    if font_path:
        kwargs.update({"fontname": "notocjk", "fontfile": str(font_path)})
    page.insert_textbox(rect, f"{page_no + 1}/{total_pages}", **kwargs)


def _append_detail_pages(
    doc: fitz.Document,
    issues: list[dict[str, Any]],
    css: str,
    font_archive: fitz.Archive | None,
) -> None:
    detail_items = _build_detail_items(issues)
    if not detail_items:
        return

    page_rect = doc[0].rect if len(doc) else fitz.Rect(0, 0, 595, 842)
    page_width = page_rect.width
    page_height = page_rect.height
    content_rect = fitz.Rect(36, 40, page_width - 36, page_height - 40)

    current: list[dict[str, Any]] = []
    for item in detail_items:
        candidate = [*current, item]
        if current and not _html_fits_rect(
            content_rect, _build_detail_html(candidate), css, font_archive
        ):
            _render_detail_page(
                doc, page_width, page_height, content_rect, current, css, font_archive
            )
            current = [item]
        else:
            current = candidate
    if current:
        _render_detail_page(doc, page_width, page_height, content_rect, current, css, font_archive)


def _render_detail_page(
    doc: fitz.Document,
    page_width: float,
    page_height: float,
    rect: fitz.Rect,
    items: list[dict[str, Any]],
    css: str,
    font_archive: fitz.Archive | None,
) -> None:
    page = doc.new_page(width=page_width, height=page_height)
    page.draw_rect(page.rect, color=None, fill=(1, 1, 1), width=0)
    page.insert_htmlbox(
        rect,
        _build_detail_html(items),
        css=css,
        archive=font_archive,
        scale_low=0.7,
        _scale_word_width=False,
    )


def _build_detail_items(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for issue in _merge_detail_issues(issues):
        detail_content = issue["detail_content"]
        chunks = _split_detail_text(detail_content)
        for chunk_no, chunk in enumerate(chunks, start=1):
            result.append(
                {
                    "page_idx": issue["page_idx"],
                    "title": issue["title"]
                    if len(chunks) == 1
                    else f"{issue['title']}（续 {chunk_no}/{len(chunks)}）",
                    "content": chunk,
                }
            )
    return result


def _merge_detail_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    order: list[tuple[Any, ...]] = []
    for index, issue in enumerate(issues):
        detail_content = str(issue.get("detail_content") or "").strip()
        if not detail_content:
            continue
        detail_content = _normalize_detail_page_content(detail_content)
        key = _detail_merge_key(issue, index)
        if key not in grouped:
            grouped[key] = {
                "page_idx": issue["page_idx"],
                "title": issue["title"],
                "contents": [],
            }
            order.append(key)
        grouped[key]["contents"].append(detail_content)

    merged = []
    for key in order:
        group = grouped[key]
        merged.append(
            {
                "page_idx": group["page_idx"],
                "title": group["title"],
                "detail_content": _merge_detail_contents(group["contents"]),
            }
        )
    return merged


def _detail_merge_key(issue: dict[str, Any], fallback_index: int) -> tuple[Any, ...]:
    meta = issue.get("meta")
    if isinstance(meta, dict) and (meta.get("item_no") is not None or meta.get("violation_code")):
        return (
            issue.get("page_idx"),
            issue.get("title"),
            meta.get("item_no"),
            meta.get("violation_code"),
        )
    return (issue.get("page_idx"), issue.get("title"), fallback_index)


def _merge_detail_contents(contents: list[str]) -> str:
    unique_contents = unique_texts(contents)
    if len(unique_contents) <= 1:
        return unique_contents[0] if unique_contents else ""

    bases = []
    reasons = []
    for content in unique_contents:
        base, sep, reason = content.partition("原因：")
        bases.append(base.strip())
        if sep and reason.strip():
            reasons.append(trim_text_end(reason.strip()))
        else:
            reasons.append(trim_text_end(content.strip()))

    unique_bases = unique_texts([base for base in bases if base])
    unique_reasons = unique_texts([reason for reason in reasons if reason])
    if len(unique_bases) == 1 and unique_reasons:
        return f"{unique_bases[0]}原因：" + "；".join(unique_reasons) + "。"
    return "；".join(trim_text_end(content) for content in unique_contents) + "。"


def _normalize_detail_page_content(text: str) -> str:
    return text.replace("本页隐患", "隐患", 1) if text.startswith("本页隐患") else text


def _split_detail_text(text: str, max_chars: int = 1000) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    chunks = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        candidate = remaining[:max_chars]
        window_start = max(0, max_chars - 160)
        break_chars = "。！？；\n"
        break_pos = max(candidate.rfind(char, window_start) for char in break_chars)
        if break_pos < window_start:
            break_pos = max_chars
        else:
            break_pos += 1
        chunks.append(remaining[:break_pos].strip())
        remaining = remaining[break_pos:].strip()
    return [chunk for chunk in chunks if chunk]


def _build_detail_html(items: list[dict[str, Any]]) -> str:
    parts = [
        "<body>",
        "<h1>审核批注明细</h1>",
        "<p class='summary'>以下为侧边栏批注对应的完整说明。</p>",
    ]
    for index, item in enumerate(items, start=1):
        parts.extend(
            [
                "<div class='card normal'>",
                f"<div class='title'>{index}. {_escape(item['title'])}</div>",
                "<div class='body'>",
                f"<p><b>原报告第 {int(item['page_idx']) + 1} 页</b></p>",
                f"<p>{_escape(item['content'])}</p>",
                "</div>",
                "</div>",
            ]
        )
    parts.append("</body>")
    return "".join(parts)


def _build_sidebar_html(
    issues: list[dict[str, Any]],
    page_no: int,
    options: SidebarAnnotationOptions,
    *,
    compact: bool = False,
    hidden_count: int = 0,
    continuation_no: int = 0,
    total_issue_count: int | None = None,
) -> str:
    issue_count = len(issues) + hidden_count
    display_total = total_issue_count if total_issue_count is not None else issue_count
    if continuation_no and display_total:
        summary = f"本页问题 {display_total} 条，本续页显示 {len(issues)} 条"
    else:
        summary = f"本页问题 {issue_count} 条" if issue_count else "本页未发现问题"
    heading = f"第 {page_no + 1} 页审核批注"
    if continuation_no:
        heading += f"（续 {continuation_no}）"
    parts = [
        "<body>",
        f"<h1>{heading}</h1>",
        f"<p class='summary'>{_escape(summary)}</p>",
    ]

    if issue_count == 0:
        if options.show_clean_page_box:
            parts.append("<div class='empty'>本页没有规则命中项。</div>")
    else:
        for idx, issue in enumerate(issues, start=1):
            klass = _severity_class(issue["severity"])
            parts.extend(
                [
                    f"<div class='card {klass}'>",
                    f"<div class='title'>{idx}. {_escape(issue['title'])}</div>",
                    "<div class='body'>",
                ]
            )
            content = issue["content"]
            if compact:
                content = _truncate_text(content, min(46, options.max_note_chars))
            parts.append(_escape(content))
            parts.extend(["</div>", "</div>"])

        if hidden_count:
            parts.append(
                f"<div class='overflow'>另有 {hidden_count} 条批注因侧栏空间不足未显示。</div>"
            )

    parts.append("</body>")
    return "".join(parts)


def _build_sidebar_css(regular_font_name: str | None, bold_font_name: str | None) -> str:
    font_face = ""
    font_family = "sans-serif"
    font_weight_regular = "400"
    font_weight_bold = "700"
    if regular_font_name:
        font_face = f"""
@font-face {{
  font-family: SidebarCJK;
  src: url({regular_font_name});
  font-weight: 400;
}}
"""
        if bold_font_name:
            font_face += f"""
@font-face {{
  font-family: SidebarCJK;
  src: url({bold_font_name});
  font-weight: 700;
}}
"""
        font_family = "SidebarCJK"
    else:
        font_weight_regular = "normal"
        font_weight_bold = "bold"

    return f"""
{font_face}
body {{
  font-family: {font_family};
  font-weight: {font_weight_regular};
  color: #1f2933;
  font-size: 10px;
  line-height: 1.5;
  word-break: break-all;
  overflow-wrap: anywhere;
}}
h1 {{
  margin: 0 0 8px 0;
  font-size: 15.5px;
  font-weight: {font_weight_bold};
  color: #111827;
}}
.summary {{
  margin: 0 0 14px 0;
  color: #4b5563;
  font-size: 10.5px;
}}
.empty {{
  margin-top: 14px;
  padding: 12px;
  border: 1px solid #d1d5db;
  background: #ffffff;
  color: #4b5563;
}}
.card {{
  margin: 0 0 10px 0;
  border: 1px solid #9ca3af;
  background: #ffffff;
  page-break-inside: avoid;
}}
.title {{
  padding: 6px 8px;
  font-size: 11px;
  font-weight: {font_weight_bold};
}}
.body {{
  padding: 7px 8px 8px 8px;
}}
.serious {{
  border-color: #b91c1c;
}}
.serious .title {{
  color: #b91c1c;
  background: #fee2e2;
}}
.normal {{
  border-color: #b45309;
}}
.normal .title {{
  color: #b45309;
  background: #fef3c7;
}}
.notice {{
  border-color: #1d4ed8;
}}
.notice .title {{
  color: #1d4ed8;
  background: #dbeafe;
}}
.overflow {{
  margin-top: 8px;
  padding: 8px;
  border: 1px solid #b91c1c;
  background: #fee2e2;
  color: #991b1b;
}}
"""


def _merge_legacy_content(item: dict[str, Any]) -> str:
    parts = []
    for field in ("reason", "suggestion"):
        value = str(item.get(field) or "").strip()
        if value:
            parts.append(value)
    return "；".join(parts)


def _group_by_page(annotations: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in annotations:
        grouped.setdefault(item["page_idx"], []).append(item)
    return grouped


def _truncate_text(text: str, max_chars: int) -> str:
    max_chars = max(1, max_chars)
    if len(text) <= max_chars:
        return text

    candidate = text[:max_chars]
    # 优先在句读或空白处截断，避免侧边栏出现“复……”这类半截词。
    window_start = max(0, max_chars - 24)
    break_chars = "。！？；，、,.!?; \n"
    break_pos = max(candidate.rfind(char, window_start) for char in break_chars)
    if break_pos >= window_start:
        candidate = candidate[:break_pos]
    elif max_chars > 6:
        candidate = candidate[: max_chars - 4]

    return candidate.rstrip("，。；、,. ;!?！？\n") + "……"


def trim_text_end(value: str) -> str:
    return value.rstrip("。.!！?？；;，,、 \n")


def unique_texts(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _severity_class(severity: str) -> str:
    return {
        "严重": "serious",
        "一般": "normal",
        "提醒": "notice",
    }.get(severity, "normal")


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _find_font_path(font_paths: list[str]) -> Path | None:
    for font_path in font_paths:
        path = Path(font_path)
        if path.exists():
            return path
    return None


# ---------- mark_text 正文高亮 ----------


def _normalize_mark_texts(value: Any) -> list[str]:
    """从原始 mark_text 字段清洗出待高亮的文本列表。兼容单个字符串与序列，去除空值与重复项。"""

    if value is None:
        return []
    if isinstance(value, str):
        candidates: list[Any] = [value]
    elif isinstance(value, (list, tuple, set)):
        candidates = list(value)
    else:
        return []

    seen: set[str] = set()
    result: list[str] = []
    for raw in candidates:
        text = str(raw or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _detect_table_cells(page: fitz.Page) -> list[fitz.Rect]:
    """识别页面内所有表格单元格 bbox。

    PyMuPDF 的 ``find_tables`` 在有明确框线的报告表格上表现稳定；识别失败时
    返回空列表，调用方会回退到文本 bbox 高亮。
    """
    rects: list[fitz.Rect] = []
    try:
        tables = page.find_tables()
    except Exception:
        return rects
    for table in getattr(tables, "tables", []) or []:
        for cell in getattr(table, "cells", []) or []:
            if cell is None:
                continue
            try:
                rect = fitz.Rect(cell)
            except Exception:
                continue
            if rect.is_empty or rect.is_infinite:
                continue
            rects.append(rect)
    return rects


def _find_enclosing_cell(hit: fitz.Rect, cell_rects: list[fitz.Rect]) -> fitz.Rect | None:
    """查找包含 hit 中心点的单元格，优先选面积较小的以避免套入整表。"""
    if not cell_rects:
        return None
    center = fitz.Point((hit.x0 + hit.x1) / 2, (hit.y0 + hit.y1) / 2)
    candidates = [cell for cell in cell_rects if cell.contains(center)]
    if not candidates:
        return None
    return min(candidates, key=lambda r: max(r.get_area(), 1.0))


def _pad_rect(rect: fitz.Rect, padding: float) -> fitz.Rect:
    return fitz.Rect(
        rect.x0 - padding,
        rect.y0 - padding,
        rect.x1 + padding,
        rect.y1 + padding,
    )


def _dedup_rects(rects: list[fitz.Rect], tolerance: float = 1.0) -> list[fitz.Rect]:
    """按近似坐标去重，避免同一单元格被多次绘制。"""
    unique: list[fitz.Rect] = []
    for rect in rects:
        if any(
            abs(rect.x0 - exist.x0) <= tolerance
            and abs(rect.y0 - exist.y0) <= tolerance
            and abs(rect.x1 - exist.x1) <= tolerance
            and abs(rect.y1 - exist.y1) <= tolerance
            for exist in unique
        ):
            continue
        unique.append(rect)
    return unique


def _search_text_rects(page: fitz.Page, text: str) -> list[fitz.Rect]:
    """在页面上查找 mark_text 出现位置。search_for 异常时回退为空，不阻断渲染。"""
    try:
        return list(page.search_for(text) or [])
    except Exception:
        return []


def _collect_mark_text_rects(
    src_page: fitz.Page,
    issues: list[dict[str, Any]],
) -> list[fitz.Rect]:
    """汇总本页所有 mark_text 对应的高亮矩形：优先按表格单元格，识别不到时回退文本 bbox。"""
    mark_texts: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        for text in _normalize_mark_texts(issue.get("mark_text")):
            if text in seen:
                continue
            seen.add(text)
            mark_texts.append(text)
    if not mark_texts:
        return []

    cell_rects = _detect_table_cells(src_page)
    rects: list[fitz.Rect] = []
    for text in mark_texts:
        for hit in _search_text_rects(src_page, text):
            if hit.is_empty or hit.is_infinite:
                continue
            cell = _find_enclosing_cell(hit, cell_rects)
            if cell is not None:
                rects.append(cell)
            else:
                rects.append(_pad_rect(hit, MARK_HIGHLIGHT_FALLBACK_PADDING))
    return _dedup_rects(rects)


def _apply_mark_text_highlights(
    src_page: fitz.Page,
    new_page: fitz.Page,
    issues: list[dict[str, Any]],
) -> None:
    """在 new_page 左侧原页区域内，依据 issues 的 mark_text 描出表格单元格高亮。

    不修改源 PDF，直接在新页上以半透明黄底描出表格格子，避免侧边栏之外发生越界。
    """
    if not issues:
        return
    rects = _collect_mark_text_rects(src_page, issues)
    if not rects:
        return

    src_bounds = src_page.rect
    for rect in rects:
        # PyMuPDF 的 search_for / find_tables 均在原页坐标系，与 new_page 左侧区域重合。
        clipped = rect & src_bounds
        if clipped.is_empty or clipped.is_infinite:
            continue
        new_page.draw_rect(
            clipped,
            color=MARK_HIGHLIGHT_BORDER,
            fill=MARK_HIGHLIGHT_FILL,
            fill_opacity=MARK_HIGHLIGHT_FILL_OPACITY,
            stroke_opacity=MARK_HIGHLIGHT_STROKE_OPACITY,
            width=MARK_HIGHLIGHT_BORDER_WIDTH,
            overlay=True,
        )
