# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""MinerU 官方公网 ZIP API 适配器，输出兼容现有 PDFParse 契约。"""

import base64
import io
import logging
import time
import uuid
import zipfile
from pathlib import PurePosixPath
from typing import Any

import requests

from app.core.config import settings


class MinerUCloudZipClient:
    """调用 MinerU 官方异步 ZIP API，并转换为现有 `/file_parse` 风格响应。"""

    def __init__(
        self,
        *,
        api_base: str,
        token: str,
        model_version: str = "vlm",
        language: str = "ch",
        poll_interval_seconds: float = 5.0,
        max_polls: int = 120,
        timeout_seconds: float = 120.0,
        enable_table: bool = True,
        enable_formula: bool = True,
        session: requests.Session | None = None,
    ):
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.model_version = model_version
        self.language = language
        self.poll_interval_seconds = poll_interval_seconds
        self.max_polls = max_polls
        self.timeout_seconds = timeout_seconds
        self.enable_table = enable_table
        self.enable_formula = enable_formula
        self.session = session or requests.Session()

    @classmethod
    def from_config(cls) -> "MinerUCloudZipClient":
        if not settings.mineru_token:
            raise ValueError("MINERU_PROVIDER=cloud_zip 时必须配置 MINERU_TOKEN")
        return cls(
            api_base=settings.mineru_api_base,
            token=settings.mineru_token,
            model_version=settings.mineru_model_version,
            language=settings.mineru_language,
            poll_interval_seconds=settings.mineru_poll_interval_seconds,
            max_polls=settings.mineru_max_polls,
            timeout_seconds=settings.mineru_timeout_seconds,
            enable_table=settings.mineru_enable_table,
            enable_formula=settings.mineru_enable_formula,
        )

    def parse_pdf_bytes(self, pdf_bytes: bytes, need_image: str = "false") -> dict[str, Any]:
        file_name = "document.pdf"
        data_id = f"doc_{uuid.uuid4().hex}"
        headers = self._headers()
        batch_url = f"{self.api_base}/api/v4/file-urls/batch"
        payload = {
            "files": [{"name": file_name, "data_id": data_id, "is_ocr": True}],
            "model_version": self.model_version,
            "language": self.language,
            "enable_formula": self.enable_formula,
            "enable_table": self.enable_table,
        }

        response = self.session.post(
            batch_url, headers=headers, json=payload, timeout=self.timeout_seconds
        )
        response.raise_for_status()
        batch_payload = response.json()
        if batch_payload.get("code") != 0:
            raise RuntimeError(f"MinerU 云端解析创建任务失败: {batch_payload.get('msg')}")

        data = batch_payload.get("data") or {}
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls") or data.get("files") or []
        if not batch_id or not file_urls:
            raise RuntimeError("MinerU 云端解析创建任务响应缺少 batch_id 或上传 URL")

        upload_response = self.session.put(
            file_urls[0], data=pdf_bytes, timeout=self.timeout_seconds
        )
        upload_response.raise_for_status()

        zip_url = self._poll_full_zip_url(batch_id, data_id, file_name)
        zip_response = self.session.get(zip_url, timeout=self.timeout_seconds)
        zip_response.raise_for_status()
        return convert_mineru_zip_to_response(
            zip_response.content,
            file_name=file_name,
            include_images=str(need_image).lower() == "true",
        )

    def _poll_full_zip_url(self, batch_id: str, data_id: str, file_name: str) -> str:
        poll_url = f"{self.api_base}/api/v4/extract-results/batch/{batch_id}"
        headers = self._headers()
        for _ in range(self.max_polls):
            response = self.session.get(poll_url, headers=headers, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if payload.get("code") != 0:
                raise RuntimeError(f"MinerU 云端解析轮询失败: {payload.get('msg')}")
            for result in normalize_extract_results(payload.get("data") or {}):
                if (
                    result.get("data_id") not in (None, data_id)
                    and result.get("file_name") != file_name
                ):
                    continue
                state = result.get("state")
                if state == "done":
                    zip_url = result.get("full_zip_url")
                    if not zip_url:
                        raise RuntimeError("MinerU 云端解析完成但缺少 full_zip_url")
                    return zip_url
                if state == "failed":
                    raise RuntimeError(
                        f"MinerU 云端解析失败: {result.get('err_msg') or result.get('message') or result}"
                    )
            time.sleep(self.poll_interval_seconds)
        raise TimeoutError(f"MinerU 云端解析轮询超时: batch_id={batch_id}")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }


def normalize_extract_results(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = data.get("extract_result", [])
    if isinstance(result, dict):
        return [result]
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    return []


def convert_mineru_zip_to_response(
    zip_bytes: bytes, *, file_name: str, include_images: bool = False
) -> dict[str, Any]:
    """把官方 ZIP 结果转换为现有 `/file_parse` 兼容响应结构。"""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = archive.namelist()
        md_name = find_first_member(names, suffix=".md")
        content_list_name = find_first_member(names, suffix="_content_list.json")
        middle_json_name = find_first_existing_member(
            names, ("layout.json", "_middle.json", "_middle_json.json")
        )

        if not md_name or not content_list_name:
            raise ValueError("MinerU ZIP 缺少 Markdown 或 content_list JSON")

        md_content = archive.read(md_name).decode("utf-8")
        content_list = archive.read(content_list_name).decode("utf-8")
        middle_json = archive.read(middle_json_name).decode("utf-8") if middle_json_name else ""
        images = read_zip_images(archive) if include_images else {}

    logging.info("MinerU 云端 ZIP 解析成功")
    return {
        "file_names": [file_name],
        "results": {
            file_name: {
                "md_content": md_content,
                "content_list": content_list,
                "middle_json": middle_json,
                "images": images,
            }
        },
    }


def find_first_member(names: list[str], *, suffix: str) -> str:
    candidates = [name for name in names if name.endswith(suffix) and not name.endswith("/")]
    if suffix == ".md":
        candidates = [name for name in candidates if "/images/" not in name]
    return sorted(candidates, key=lambda name: (name.count("/"), name))[0] if candidates else ""


def find_first_existing_member(names: list[str], suffixes: tuple[str, ...]) -> str:
    for suffix in suffixes:
        found = find_first_member(names, suffix=suffix)
        if found:
            return found
    return ""


def read_zip_images(archive: zipfile.ZipFile) -> dict[str, str]:
    images: dict[str, str] = {}
    for name in archive.namelist():
        path = PurePosixPath(name)
        if "images" not in path.parts or name.endswith("/"):
            continue
        if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
            continue
        image_key = "/".join(path.parts[path.parts.index("images") :])
        images[image_key] = base64.b64encode(archive.read(name)).decode("utf-8")
    return images
