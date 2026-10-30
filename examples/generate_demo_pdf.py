#!/usr/bin/env python3
# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""生成无业务含义的通用示例 PDF。"""

from __future__ import annotations

import argparse
from pathlib import Path

import pymupdf


def build_pdf(output: Path) -> None:
    """写入一页通用项目总结，供 mock 解析与规则链路演示使用。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "# Project Summary", fontname="helv")
        page.insert_text((72, 110), "Materials submitted: yes", fontname="helv")
        page.insert_text((72, 130), "Traceability: available", fontname="helv")
        pdf.save(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a generic demo PDF")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("examples/generated/project-summary.pdf"),
    )
    args = parser.parse_args()
    build_pdf(args.output)
    print(f"Generated {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
