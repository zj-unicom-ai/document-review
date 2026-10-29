# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-007 平台超管初始密码解析测试。"""

from __future__ import annotations

from app.bootstrap.initialize_superadmin import (
    DEFAULT_SUPERADMIN_INITIAL_PASSWORD,
    resolve_initial_password,
)


def test_bl007_default_initial_password_is_fixed() -> None:
    assert DEFAULT_SUPERADMIN_INITIAL_PASSWORD == "Changeme@2026"


def test_bl007_env_password_takes_precedence() -> None:
    password = resolve_initial_password({"SUPERADMIN_INITIAL_PASSWORD": "env-password"})

    assert password == "env-password"


def test_bl007_missing_env_uses_default_password() -> None:
    assert resolve_initial_password({}) == "Changeme@2026"
