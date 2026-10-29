# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""MinerU 调用与本地 artifact 构建边界。"""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import shutil
import uuid

try:
    import fcntl
except ImportError:  # pragma: no cover 非 POSIX 部署暂无进程级文件锁实现
    fcntl = None
from pathlib import Path
from typing import Any

import requests

from app.core.config import settings


def _mineru_bool(value: Any) -> str:
    return "true" if str(value).lower() == "true" else "false"


@contextlib.contextmanager
def _artifact_build_lock(output_dir: Path):
    """以 artifact 目录为粒度跨进程串行化构建，避免并发删除 / 重命名竞争。"""
    lock_path = output_dir.parent / f".{output_dir.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock_file:
        if fcntl is not None:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


class PDFParse:
    """调用 MinerU 并把响应落成平台标准 artifact。"""

    def __init__(self, settings_instance=None):
        self.settings = settings_instance or settings
        self.mineru_api_url = self.settings.mineru_private_api_server

    def parse_pdf_with_mineru(self, pdf_bytes: bytes, need_image: str) -> dict:
        """按 self-host `/file_parse` 契约调用 MinerU。"""
        cfg = self.settings
        if str(cfg.mineru_provider).lower() == "cloud_zip":
            from app.utils.mineru_cloud_zip_client import MinerUCloudZipClient

            return MinerUCloudZipClient.from_config().parse_pdf_bytes(
                pdf_bytes, need_image=need_image
            )

        if not self.mineru_api_url:
            raise ValueError("MinerU API URL 未配置")

        files = {"files": ("document.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        data = {
            "return_middle_json": "true",
            "return_model_output": "false",
            "return_md": "true",
            "return_images": need_image,
            "end_page_id": "128",
            "parse_method": "auto",
            "start_page_id": "0",
            "lang_list": cfg.mineru_language,
            "return_content_list": "true",
            "backend": cfg.mineru_private_backend,
            "table_enable": _mineru_bool(cfg.mineru_enable_table),
            "response_format_zip": "false",
            "return_original_file": "false",
            "formula_enable": _mineru_bool(cfg.mineru_enable_formula),
        }
        response = requests.post(
            self.mineru_api_url,
            files=files,
            data=data,
            timeout=cfg.mineru_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def get_pdf_artifact_bundle(self, pdf_bytes: bytes, need_image: str = "false") -> dict:
        """调用 MinerU 并返回可写入 artifact 的 md / content_list / middle / images。"""
        results = self.parse_pdf_with_mineru(pdf_bytes, need_image=need_image)
        file_names = results.get("file_names") or []
        if not file_names:
            raise ValueError("MinerU 返回结果缺少 file_names")
        file_name = file_names[0]
        file_result = (results.get("results") or {}).get(file_name)
        if not file_result:
            raise ValueError(f"MinerU 返回结果缺少 {file_name}")

        markdown = file_result.get("md_content") or ""
        if not markdown:
            raise ValueError("MinerU 返回的 md_content 为空")
        raw_content_list = file_result.get("content_list") or "[]"
        try:
            content_list = json.loads(raw_content_list)
        except json.JSONDecodeError as exc:
            raise ValueError("MinerU 返回的 content_list JSON 不合法") from exc

        middle_json = file_result.get("middle_json") or {}
        if isinstance(middle_json, str) and middle_json.strip():
            try:
                middle_json = json.loads(middle_json)
            except json.JSONDecodeError:
                middle_json = {}
        images = file_result.get("images") or {}
        return {
            "markdown": markdown,
            "content_list": content_list,
            "middle_json": middle_json,
            "images": images,
        }

    @classmethod
    async def locate_or_build_artifact_async(
        cls,
        source_path: Path,
        *,
        output_dir: Path,
        parser: PDFParse | None = None,
    ) -> Path:
        return await asyncio.to_thread(
            cls.locate_or_build_artifact_sync,
            source_path,
            output_dir=output_dir,
            parser=parser,
        )

    @classmethod
    def locate_or_build_artifact_sync(
        cls,
        source_path: Path,
        *,
        output_dir: Path,
        parser: PDFParse | None = None,
    ) -> Path:
        """已有完整 artifact 时复用；否则调用 MinerU 生成。"""
        if parser is not None and hasattr(parser, "locate_or_build_artifact_sync"):
            return parser.locate_or_build_artifact_sync(
                source_path, output_dir=output_dir, parser=parser
            )
        with _artifact_build_lock(output_dir):
            required = [output_dir / "full.md", output_dir / "layout.json"]
            if output_dir.is_dir():
                entries = list(output_dir.iterdir())
                if (
                    all(path.is_file() for path in required)
                    and any(path.name.endswith("_content_list.json") for path in entries)
                    and any(path.name.endswith("_origin.pdf") for path in entries)
                ):
                    return output_dir
            return cls.build_artifact_sync(source_path, output_dir=output_dir, parser=parser)

    @classmethod
    async def build_artifact_async(
        cls,
        source_path: Path,
        *,
        output_dir: Path,
        parser: PDFParse | None = None,
    ) -> Path:
        return await asyncio.to_thread(
            cls.build_artifact_sync,
            source_path,
            output_dir=output_dir,
            parser=parser,
        )

    @classmethod
    def build_artifact_sync(
        cls,
        source_path: Path,
        *,
        output_dir: Path,
        parser: PDFParse | None = None,
    ) -> Path:
        """把 MinerU 响应原子写入标准 artifact 目录。"""
        try:
            source_path = Path(source_path)
            if not source_path.is_file():
                raise FileNotFoundError(f"待解析 PDF 不存在: {source_path}")
            mineru = parser or cls()
            bundle = mineru.get_pdf_artifact_bundle(source_path.read_bytes())
            output_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = output_dir.parent / f".{output_dir.name}.{uuid.uuid4().hex}"
            temp_dir.mkdir()
            (temp_dir / "full.md").write_text(bundle["markdown"], encoding="utf-8")
            (temp_dir / "upload_content_list.json").write_text(
                json.dumps(bundle["content_list"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (temp_dir / "layout.json").write_text(
                json.dumps(bundle["middle_json"], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            shutil.copyfile(source_path, temp_dir / "upload_origin.pdf")
            if output_dir.exists():
                shutil.rmtree(output_dir)
            temp_dir.rename(output_dir)
            return output_dir
        except Exception as exc:
            raise RuntimeError(f"生成 MinerU artifact 失败: {exc}") from exc
