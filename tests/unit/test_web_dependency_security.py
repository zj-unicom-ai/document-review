# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""前端 lockfile 安全回归测试。"""

from __future__ import annotations

import json
from pathlib import Path


def test_bl114_source_map_js_is_not_vulnerable_version() -> None:
    """锁定已知受 GHSA-68fv-2mgg-jv7q 影响的版本即失败。"""
    lockfile = json.loads(
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("web", "package-lock.json")
        .read_text(encoding="utf-8")
    )
    versions = [
        package.get("version")
        for key, package in lockfile.get("packages", {}).items()
        if key.endswith("node_modules/source-map-js")
    ]

    assert versions
    assert "1.2.1" not in versions


def test_bl125_a1_vite_and_vitest_are_at_least_fixed_versions() -> None:
    """拦截 2026-10 开发工具链安全公告的已知受影响锁定版本。"""
    lockfile = json.loads(
        Path(__file__)
        .resolve()
        .parents[2]
        .joinpath("web", "package-lock.json")
        .read_text(encoding="utf-8")
    )
    packages = lockfile["packages"]

    def version(name: str) -> tuple[int, ...]:
        return tuple(int(part) for part in packages[f"node_modules/{name}"]["version"].split("."))

    assert version("vite") >= (7, 3, 7)
    assert version("vitest") >= (5, 0, 5)
