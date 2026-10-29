# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-007 运维手册备份命令回归测试。"""

from __future__ import annotations

from pathlib import Path


def test_bl007_a4_backup_directory_is_writable() -> None:
    """备份命令需要写入 storage.tgz，不能把宿主机备份目录挂载为只读。"""
    text = Path("docs/operations.md").read_text(encoding="utf-8")
    backup_section = text.split("## 备份", 1)[1].split("## 恢复", 1)[0]

    assert ":/backup:ro" not in backup_section
    assert '-v "$(pwd)/backup/$(date +%F)":/backup' in backup_section
