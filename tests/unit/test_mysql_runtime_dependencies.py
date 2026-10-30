# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""MySQL 运行时依赖回归测试。"""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_bl112_pymysql_declares_rsa_extra() -> None:
    """MySQL 8 重启后需要 RSA 认证支持，不能只安装基础 PyMySQL。"""
    pyproject = tomllib.loads(
        Path(__file__).resolve().parents[2].joinpath("pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = pyproject["project"]["dependencies"]

    assert "PyMySQL[rsa]>=1.1" in dependencies
