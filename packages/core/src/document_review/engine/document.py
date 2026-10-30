# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""文档解析结果与规则可见的 DocumentContext。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from document_review.operators.base import OperatorContext
from document_review.schemas.profile import ConceptBinding
from document_review.utils.mineru_table import parse_table_rows, strip_html_tags


@dataclass(slots=True)
class ParsedDocument:
    """本地解析产物聚合；所有坐标必须显式标注单位。"""

    markdown: str
    blocks: list[dict[str, Any]]
    layout: dict[str, Any] | list[Any]
    pdf_path: Path
    page_count: int
    images: list[dict[str, Any]] = field(default_factory=list)
    page_texts: list[str] = field(default_factory=list)


class DocumentContext:
    """规则的唯一文档视图；profile 绑定优先，模板 locator 兜底。"""

    def __init__(self, parsed: ParsedDocument, profile: dict[str, Any] | None = None):
        self.parsed = parsed
        self.profile = profile or {}
        self._bindings = self._load_bindings()
        self._tables = self._load_tables()
        self._sections = self._load_sections()

    def __reduce__(self):
        """支持 MemorySaver 序列化；重建时会按同一解析产物重算派生索引。"""
        return (self.__class__, (self.parsed, self.profile))

    def resolve(self, concept: str) -> ConceptBinding | None:
        return self._bindings.get(concept)

    def get_section_text(self, binding: ConceptBinding, max_chars: int = 8000) -> str:
        selected: set[int] = set()
        for target in binding.targets:
            pattern = target.locator.get("section_title_regex")
            if pattern:
                regex = re.compile(pattern)
                for idx, block in enumerate(self.parsed.blocks):
                    level = block.get("text_level")
                    if level is None or not regex.search(str(block.get("text", ""))):
                        continue
                    selected.add(idx)
                    for following in range(idx + 1, len(self.parsed.blocks)):
                        next_level = self.parsed.blocks[following].get("text_level")
                        if next_level is not None and next_level <= level:
                            break
                        selected.add(following)
            elif target.page_idx is not None:
                selected.update(
                    idx
                    for idx, block in enumerate(self.parsed.blocks)
                    if block.get("page_idx") == target.page_idx
                )
        return "\n".join(self.block_text(self.parsed.blocks[idx]) for idx in sorted(selected))[
            :max_chars
        ]

    @staticmethod
    def block_text(block: dict[str, Any]) -> str:
        """统一返回正文、表格及图片说明中的可读文本。"""
        parts = [str(block.get("text") or "")]
        html = block.get("table_body") or block.get("html")
        if html:
            parts.extend(" | ".join(row) for row in parse_table_rows(html))
        for key in ("image_caption", "image_footnote", "table_caption", "table_footnote"):
            value = block.get(key) or []
            parts.extend([value] if isinstance(value, str) else map(str, value))
        return "\n".join(part for part in parts if part)

    def get_table(self, binding: ConceptBinding) -> list[dict[str, str]]:
        tables = self._binding_tables(binding)
        return tables[0]["rows"] if tables else []

    def get_table_text(self, binding: ConceptBinding, max_chars: int = 8000) -> str:
        """按绑定定位符返回精确表格文本，不把同页无关正文混入。"""
        return "\n".join(table["text"] for table in self._binding_tables(binding))[:max_chars]

    def get_table_fields(self, binding: ConceptBinding, aliases: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        wanted = {self._normalize(alias) for alias in aliases}
        for table in self._binding_tables(binding):
            for row in table["raw_rows"]:
                cells = [self._normalize(cell) for cell in row]
                for idx, cell in enumerate(cells):
                    if cell in wanted and idx + 1 < len(row):
                        value = str(row[idx + 1]).strip()
                        if value:
                            result[self._original_alias(cell, aliases)] = value
            for row in table["rows"]:
                for key, value in row.items():
                    if self._normalize(key) in wanted:
                        result[self._original_alias(self._normalize(key), aliases)] = str(value)
        return result

    def get_images(
        self,
        binding: ConceptBinding | None = None,
        page_idx: int | None = None,
    ) -> list[dict[str, Any]]:
        images = self.parsed.images
        wanted_xrefs = {
            xref
            for target in (binding.targets if binding else [])
            for xref in (target.locator.get("image_xrefs") or [])
            if isinstance(xref, int)
        }
        pages = (
            {target.page_idx for target in binding.targets if target.page_idx is not None}
            if binding
            else set()
        )
        if page_idx is not None:
            images = [image for image in images if image.get("page_idx") == page_idx]
        elif wanted_xrefs:
            images = [image for image in images if image.get("xref") in wanted_xrefs]
        elif pages:
            images = [image for image in images if image.get("page_idx") in pages]
        return list(images)

    def get_list_items(self, binding: ConceptBinding | None = None) -> list[dict[str, Any]]:
        """把绑定表格转换为通用条目列表，字段名来自表头或键名。"""
        tables = self._binding_tables(binding) if binding is not None else self._tables
        if not tables:
            return []

        locator = binding.targets[0].locator if binding is not None and binding.targets else {}
        explicit_vertical = locator.get("list_layout") == "vertical"
        items: list[dict[str, Any]] = []
        for table in tables:
            if explicit_vertical or self._looks_like_vertical_table(table):
                fields = self._fields_from_rows(table["raw_rows"])
                items.append(self._build_list_item(fields, table["page_idx"], 1))
                continue
            for row in table["rows"]:
                items.append(self._build_list_item(row, table["page_idx"], len(items) + 1))
        return items

    @staticmethod
    def _looks_like_vertical_table(table: dict[str, Any]) -> bool:
        """识别表格解析器压成“每行一个键”的纵向键值表。"""
        rows = table.get("rows") or []
        if len(rows) < 2:
            raw_rows = table.get("raw_rows") or []
            return (
                len(rows) == 1
                and len(rows[0]) == 1
                and len(raw_rows) == 2
                and all(len(row) == 2 for row in raw_rows)
            )
        key_sets = [tuple(row.keys()) for row in rows]
        if all(len(keys) == 1 for keys in key_sets) and len(set(key_sets)) > 1:
            return True
        # 纵向表第一行是“字段名 + 字段值”；表格解析器可能把字段值当表头。
        # 数字表头几乎不可能作为通用字段名，因此视为纵向表。
        headers = table.get("headers") or []
        return any(str(header).strip().isdigit() for header in headers)

    @staticmethod
    def _build_list_item(values: dict[str, Any], page_idx: int, seq: int) -> dict[str, Any]:
        item = {str(key): value for key, value in values.items() if str(value).strip()}
        no_key = next(
            (
                key
                for key in item
                if str(key).lower() in {"no", "id"} or str(key).endswith(("编号", "序号"))
            ),
            None,
        )
        explicit_no = item.get(no_key) if no_key is not None else None
        item["no"] = str(explicit_no if explicit_no not in (None, "") else seq)
        item["description"] = " / ".join(
            str(value) for value in values.values() if str(value).strip()
        )
        item["page_idx"] = page_idx
        return item

    def get_image_bytes(self, image: dict[str, Any]) -> bytes:
        """按图片引用提取字节；引用必须来自 get_images 返回值。"""
        import pymupdf

        xref = image.get("xref")
        if xref is None:
            raise ValueError("图片引用缺少 xref")
        page_idx = image.get("page_idx")
        with pymupdf.open(self.parsed.pdf_path) as pdf:
            if type(page_idx) is not int or not 0 <= page_idx < len(pdf):
                raise ValueError("图片当前页不存在")
            if int(xref) not in {item["xref"] for item in pdf[page_idx].get_image_info(xrefs=True)}:
                raise ValueError("图片 xref 不属于当前页")
            extracted = pdf.extract_image(int(xref))
        return extracted["image"]

    def read_page_text(self, page_idx: int) -> str:
        """读取单页解析文本；没有解析 block 时回退原 PDF 文本。"""
        if not 0 <= page_idx < self.parsed.page_count:
            raise ValueError("页码超出文档范围")
        blocks = [block for block in self.parsed.blocks if block.get("page_idx") == page_idx]
        text = "\n".join(self.block_text(block) for block in blocks)
        if text.strip():
            return text
        import pymupdf

        with pymupdf.open(self.parsed.pdf_path) as pdf:
            return pdf[page_idx].get_text()

    def locate_text_page(self, fragment: str, *, fallback: int | None = None) -> int | None:
        """在原 PDF 页文本中定位内容首现页；解析块跨页时不使用块起始页。"""
        normalized = self._normalize(fragment)
        if not normalized:
            return fallback
        for page_idx, text in enumerate(self.parsed.page_texts):
            if normalized in self._normalize(text):
                return page_idx
        return fallback

    def locate_image_for_text(self, fragment: str) -> dict[str, Any] | None:
        """在原 PDF 中定位与文本最近的图片，用于表格内长标题的合影等目标。"""
        normalized = self._normalize(fragment)
        if not normalized:
            return None

        import pymupdf

        with pymupdf.open(self.parsed.pdf_path) as pdf:
            for page_idx, page in enumerate(pdf):
                if normalized not in self._normalize(page.get_text()):
                    continue
                alias_rect = self._find_text_region(page, normalized)
                if alias_rect is None:
                    continue
                images = {
                    info["xref"]: info.get("bbox")
                    for info in page.get_image_info(xrefs=True)
                    if info.get("xref") is not None
                }
                registered = [
                    image
                    for image in self.parsed.images
                    if image.get("page_idx") == page_idx and image.get("xref") in images
                ]
                if not registered:
                    return None
                return min(
                    registered,
                    key=lambda image: self._rect_distance(
                        alias_rect, pymupdf.Rect(images[image["xref"]])
                    ),
                )
        return None

    def render_page(self, page_idx: int, bbox_permille: list[float] | None = None) -> bytes:
        """将当前 PDF 原页或千分比裁剪区渲染为 PNG。"""
        import pymupdf

        if not 0 <= page_idx < self.parsed.page_count:
            raise ValueError("页码超出文档范围")
        with pymupdf.open(self.parsed.pdf_path) as pdf:
            page = pdf[page_idx]
            clip = page.rect
            if bbox_permille is not None:
                x0, y0, x1, y1 = bbox_permille
                if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000):
                    raise ValueError("bbox_permille 必须为 0–1000 内有面积的矩形")
                clip = pymupdf.Rect(
                    page.rect.x0 + x0 * page.rect.width / 1000,
                    page.rect.y0 + y0 * page.rect.height / 1000,
                    page.rect.x0 + x1 * page.rect.width / 1000,
                    page.rect.y0 + y1 * page.rect.height / 1000,
                )
            scale = min(2.0, 2400 / max(clip.width, clip.height))
            return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip).tobytes("png")

    def search_text(self, pattern: str, scope: str | None = None) -> list[dict[str, Any]]:
        regex = re.compile(pattern)
        text = self.parsed.markdown if scope in (None, "document", "markdown") else ""
        return [
            {
                "text": match.group(0),
                "page_idx": self._page_for_text(match.group(0)),
                "span": match.span(),
            }
            for match in regex.finditer(text)
        ]

    def get_markdown(self, max_chars: int | None = None) -> str:
        return self.parsed.markdown if max_chars is None else self.parsed.markdown[:max_chars]

    def get_section_tree(self, *, max_sections: int = 100) -> list[dict[str, Any]]:
        """供画像发现使用的标题树（只含标题与页码）。"""
        return [
            {"title": section["title"], "page_idx": section["page_idx"]}
            for section in self._sections[:max_sections]
        ]

    def get_table_anchors(self, *, max_anchors: int = 50) -> list[dict[str, Any]]:
        """供画像发现使用的表格锚点（含受限文本摘要）。"""
        return [
            {
                "block_idx": table["block_idx"],
                "page_idx": table["page_idx"],
                "columns": list(
                    table.get("headers") or (table["rows"][0] if table["rows"] else {})
                ),
                "row_count": len(table["rows"]),
                # 复合表格首行列头代表不了后续嵌套分组，摘要用于暴露分组锚点。
                "text_excerpt": table["text"][:800],
            }
            for table in self._tables[:max_anchors]
        ]

    def get_first_page_summary(self, *, max_chars: int = 2000) -> str:
        """首页摘要：画像发现的受控输入，不送全文。"""
        parts = [
            str(block.get("text", ""))
            for block in self.parsed.blocks
            if block.get("type") == "text" and int(block.get("page_idx") or 0) == 0
        ]
        return "\n".join(parts)[:max_chars]

    def to_operator_context(self, binding: ConceptBinding) -> OperatorContext:
        target = binding.targets[0] if binding.targets else None
        kind = target.kind if target else "field"
        locator = target.locator if target else {}
        target_page = target.page_idx if target else None
        if kind == "table":
            tables = self._binding_tables(binding)
            rows = tables[0]["rows"] if tables else []
            columns = list(rows[0]) if rows else []
            fields: dict[str, str] = {}
            for table in self._binding_tables(binding):
                fields.update(self._fields_from_rows(table["raw_rows"]))
            return OperatorContext(
                fields=fields,
                table_rows=rows,
                table_columns=columns,
                sections=self._sections,
                markdown_text=self.parsed.markdown,
                anchor_page_idx=target_page,
                table_page_idx=tables[0].get("page_idx") if tables else None,
            )
        if kind == "item_list":
            return OperatorContext(
                list_items=self.get_list_items(binding),
                images=self.get_images(None),
                sections=self._sections,
                markdown_text=self.parsed.markdown,
                anchor_page_idx=target_page,
            )
        if kind == "image_group":
            return OperatorContext(
                images=self.get_images(binding),
                sections=self._sections,
                markdown_text=self.parsed.markdown,
                anchor_page_idx=target_page,
            )
        if kind == "section":
            return OperatorContext(
                sections=self._sections,
                markdown_text=self.parsed.markdown,
                anchor_page_idx=target_page,
            )
        aliases = locator.get("field_aliases", [])
        return OperatorContext(
            fields=self.get_table_fields(binding, aliases) if aliases else {},
            sections=self._sections,
            markdown_text=self.parsed.markdown,
            anchor_page_idx=target_page,
        )

    def build_evidence_context(self, evidence: Any) -> dict[str, Any]:
        """把规则声明的命名证据转换为受限摘要，供多证据规则使用。"""
        if not isinstance(evidence, dict):
            return {}
        result: dict[str, Any] = {}
        for key, spec in evidence.items():
            if not isinstance(key, str) or not isinstance(spec, dict):
                continue
            concept = str(spec.get("concept", ""))
            entry: dict[str, Any] = {
                "concept": concept,
                "required": bool(spec.get("required", True)),
            }
            binding = self.resolve(concept)
            if binding is None:
                entry.update({"found": False, "status": "not_found"})
                result[key] = entry
                continue

            try:
                ctx = self.to_operator_context(binding)
                entry.update(
                    {
                        "found": True,
                        "status": binding.status,
                        "page_idx": binding.targets[0].page_idx if binding.targets else None,
                        "fields": ctx.fields,
                        "table_rows": ctx.table_rows[:20],
                        "table_columns": ctx.table_columns,
                        "list_items": ctx.list_items[:20],
                    }
                )
                entry["found"] = bool(ctx.fields or ctx.table_rows or ctx.list_items)
                if binding.targets and binding.targets[0].kind in {"section", "image_group"}:
                    entry["section_text"] = self.get_section_text(binding, max_chars=4000)
                    entry["found"] = bool(entry["section_text"])
            except Exception as exc:
                entry.update({"found": False, "status": "resolver_error", "error": str(exc)})
            result[key] = entry
        return result

    def _load_bindings(self) -> dict[str, ConceptBinding]:
        try:
            items = [
                ConceptBinding.model_validate(item) for item in self.profile.get("bindings", [])
            ]
        except ValidationError:
            return {}
        return {item.concept_code: item for item in items}

    def _load_tables(self) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        for block_idx, block in enumerate(self.parsed.blocks):
            html = block.get("table_body") or block.get("html") or ""
            if not isinstance(html, str) or "<table" not in html.lower():
                continue
            raw_rows = parse_table_rows(html)
            data_rows = [row for row in raw_rows if len(row) > 1]
            headers = [self._normalize(cell) for cell in data_rows[0]] if data_rows else []
            rows = [
                {headers[i]: cell for i, cell in enumerate(row) if i < len(headers)}
                for row in data_rows[1:]
            ]
            tables.append(
                {
                    "block_idx": block_idx,
                    "page_idx": int(block.get("page_idx") or 0),
                    "headers": headers,
                    "raw_rows": raw_rows,
                    "rows": rows,
                    "text": strip_html_tags(html),
                }
            )
        return tables

    def _load_sections(self) -> list[dict[str, Any]]:
        sections: list[dict[str, Any]] = []
        seen: set[str] = set()
        for block in self.parsed.blocks:
            if block.get("type") == "text" and block.get("text_level") is not None:
                title = str(block.get("text", "")).strip()
                self._append_section(sections, seen, title, int(block.get("page_idx") or 0))
        for line in self.parsed.markdown.splitlines():
            match = re.match(r"^#{1,6}\s*(.+)$", line.strip())
            if match:
                self._append_section(sections, seen, match.group(1).strip(), 0)
        return sections

    @staticmethod
    def _append_section(
        sections: list[dict[str, Any]], seen: set[str], title: str, page_idx: int
    ) -> None:
        if not title or title in seen:
            return
        seen.add(title)
        sections.append({"title": title, "ordinal": None, "page_idx": page_idx, "content": ""})

    def _binding_tables(self, binding: ConceptBinding) -> list[dict[str, Any]]:
        target = binding.targets[0] if binding.targets else None
        locator = target.locator if target else {}
        keywords = locator.get("anchor_keywords", [])
        after_section = locator.get("after_section")
        block_idx = locator.get("block_idx")
        if not keywords and not after_section:
            return self._tables
        normalized = [self._normalize(keyword) for keyword in keywords]
        matched = []
        for table in self._tables:
            if isinstance(block_idx, int) and table["block_idx"] != block_idx:
                continue
            text = self._normalize(table["text"])
            if (keywords and any(keyword and keyword in text for keyword in normalized)) or (
                after_section and self._normalize(after_section) in text
            ):
                matched.append(table)
        return matched

    @staticmethod
    def _fields_from_rows(rows: list[list[str]]) -> dict[str, str]:
        fields: dict[str, str] = {}
        for row in rows:
            for idx, cell in enumerate(row):
                key = DocumentContext._normalize(cell)
                if key and idx + 1 < len(row) and str(row[idx + 1]).strip():
                    fields[key] = str(row[idx + 1]).strip()
        return fields

    @staticmethod
    def _normalize(value: Any) -> str:
        return re.sub(r"\s+", "", strip_html_tags(str(value or "")))

    @classmethod
    def _find_text_region(cls, page: Any, normalized_alias: str) -> Any | None:
        """用连续文本块滑动窗口定位跨行长别名，并返回其合并 bbox。"""
        import pymupdf

        blocks = sorted(
            [item for item in page.get_text("blocks") if len(item) >= 5],
            key=lambda item: (float(item[1]), float(item[0])),
        )
        max_window = min(len(blocks), 12)
        for size in range(1, max_window + 1):
            for start in range(0, len(blocks) - size + 1):
                selected = blocks[start : start + size]
                combined = cls._normalize("".join(str(item[4]) for item in selected))
                if normalized_alias not in combined:
                    continue
                rect = pymupdf.Rect(selected[0][:4])
                for item in selected[1:]:
                    rect.include_rect(pymupdf.Rect(item[:4]))
                return rect
        return None

    @staticmethod
    def _rect_distance(left: Any, right: Any) -> float:
        """返回矩形间距；相交/包含视为 0，优先选择文本邻近图片。"""
        dx = max(left.x0 - right.x1, right.x0 - left.x1, 0)
        dy = max(left.y0 - right.y1, right.y0 - left.y1, 0)
        return dx * dx + dy * dy

    @staticmethod
    def _original_alias(normalized: str, aliases: list[str]) -> str:
        for alias in aliases:
            if DocumentContext._normalize(alias) == normalized:
                return alias
        return normalized

    def _page_for_text(self, fragment: str) -> int:
        normalized = self._normalize(fragment)
        for block in self.parsed.blocks:
            values = [block.get("text", ""), block.get("table_body", ""), block.get("html", "")]
            if any(normalized and normalized in self._normalize(value) for value in values):
                return int(block.get("page_idx") or 0)
        return 0
