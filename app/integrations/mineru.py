# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""MinerU 解析边界与本地 artifact 解析器。"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Protocol

import pymupdf

from app.engine.document import ParsedDocument


class MineruParseError(RuntimeError):
    """本地 artifact 缺失或格式不合法。"""


class DocumentParser(Protocol):
    """解析器协议；生产实现可注入，测试不得发生网络调用。"""

    async def parse(self, path: Path) -> ParsedDocument:
        """把待审文件解析为 ParsedDocument。"""
        ...


class MineruArtifactParser:
    """读取仓库内已导出的 MinerU 结果目录。"""

    def __init__(self, artifact_dir: Path) -> None:
        self.artifact_dir = artifact_dir

    async def parse(self, path: Path) -> ParsedDocument:
        return await asyncio.to_thread(self._parse_sync, path)

    def _parse_sync(self, path: Path) -> ParsedDocument:
        markdown_path = self._required_file("full.md")
        content_path = self._preferred_file("*_content_list_v2.json", "*_content_list.json")
        layout_path = self._preferred_file("layout.json", "layout.json")
        pdf_path = self._preferred_file("*_origin.pdf", "*_origin.pdf")

        if not path.is_file():
            raise MineruParseError(f"待解析 PDF 不存在: {path}")
        markdown = markdown_path.read_text(encoding="utf-8")
        blocks = self._read_json(content_path, label="content_list")
        layout = self._read_json(layout_path, label="layout")
        blocks = self._normalize_blocks(blocks)
        if not isinstance(blocks, list) or any(not isinstance(item, dict) for item in blocks):
            raise MineruParseError("content_list 必须是对象数组")

        with pymupdf.open(pdf_path) as pdf:
            page_count = pdf.page_count
            images = self._extract_images(pdf)
            page_texts = [page.get_text() for page in pdf]

        return ParsedDocument(
            markdown=markdown,
            blocks=blocks,
            layout=layout,
            pdf_path=pdf_path,
            page_count=page_count,
            images=images,
            page_texts=page_texts,
        )

    def _required_file(self, pattern: str) -> Path:
        matches = sorted(self.artifact_dir.glob(pattern))
        if not matches:
            raise MineruParseError(f"MinerU artifact 缺少 {pattern}")
        return matches[0]

    def _preferred_file(self, preferred: str, fallback: str) -> Path:
        first = sorted(self.artifact_dir.glob(preferred))
        if first:
            return first[0]
        return self._required_file(fallback)

    def _read_json(self, path: Path, *, label: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MineruParseError(f"{label} JSON 不合法: {path.name}") from exc

    @staticmethod
    def _extract_images(pdf: pymupdf.Document) -> list[dict[str, Any]]:
        from app.utils.mineru_bbox import pt_bbox_to_permille

        images: list[dict[str, Any]] = []
        for page_idx, page in enumerate(pdf):
            for info in page.get_image_info(xrefs=True):
                bbox_permille = pt_bbox_to_permille(
                    info.get("bbox"), page.rect.width, page.rect.height
                )
                images.append(
                    {
                        "page_idx": page_idx,
                        "xref": info.get("xref"),
                        "bbox_pt": info.get("bbox"),
                        "bbox_permille": bbox_permille,
                    }
                )
        return images

    @staticmethod
    def _normalize_blocks(value: Any) -> list[dict[str, Any]]:
        """把 v2 的页数组与嵌套 content 结构归一为执行层 block 契约。"""
        if not isinstance(value, list):
            return value if isinstance(value, list) else []
        pages = value if value and all(isinstance(item, list) for item in value) else [value]
        blocks: list[dict[str, Any]] = []
        for page_idx, page_blocks in enumerate(pages):
            for raw in page_blocks:
                if not isinstance(raw, dict):
                    continue
                block = dict(raw)
                block.setdefault("page_idx", page_idx)
                content = block.get("content")
                if isinstance(content, dict):
                    html = content.get("html")
                    if isinstance(html, str):
                        block.setdefault("table_body", html)
                    texts: list[str] = []
                    for nested in content.values():
                        if not isinstance(nested, list):
                            continue
                        for item in nested:
                            if isinstance(item, dict):
                                text = item.get("content", item.get("text", ""))
                                if text:
                                    texts.append(str(text))
                    if texts:
                        block.setdefault("text", "".join(texts))
                    if block.get("type") == "title":
                        block.setdefault("text_level", content.get("level", 1))
                blocks.append(block)
        return blocks
