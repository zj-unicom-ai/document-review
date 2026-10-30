# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-117 Python 依赖锁与 Docker 构建契约测试。"""

from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[2]
LOCAL_PACKAGES = {"document-review", "document-review-core"}


def _external_dependencies() -> set[str]:
    names: set[str] = set()
    for relative in ("pyproject.toml", "packages/core/pyproject.toml"):
        data = tomllib.loads((ROOT / relative).read_text(encoding="utf-8"))
        for item in data["project"]["dependencies"]:
            requirement = Requirement(item)
            if canonicalize_name(requirement.name) not in LOCAL_PACKAGES:
                names.add(canonicalize_name(requirement.name))
    return names


def _locked_blocks() -> list[str]:
    """按顶格 requirement 行分组，hash 行保持在其对应块内。"""
    blocks: list[str] = []
    current: list[str] = []
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if line and not line[0].isspace():
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return [block for block in blocks if "==" in block]


def test_bl117_a1_e1_all_runtime_dependencies_are_locked() -> None:
    """pyproject 声明的外部运行时依赖必须全部进入锁文件。"""
    locked = {canonicalize_name(block.split("==", 1)[0].strip()) for block in _locked_blocks()}
    expected = _external_dependencies()

    assert expected
    assert expected <= locked


def test_bl117_a1_e2_every_locked_requirement_has_hash() -> None:
    """锁文件中的每个精确版本 requirement 都必须携带 hash。"""
    blocks = _locked_blocks()

    assert blocks
    assert all("--hash=sha256:" in block for block in blocks)


def test_bl117_a1_lock_uses_fixed_resolution_cutoff() -> None:
    """上游刚发布新版本时，锁文件复现也不能悄悄切换版本。"""
    header = "\n".join(
        line
        for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines()[:4]
        if line.startswith("#")
    )

    assert "--exclude-newer=" in header


def test_bl117_a1_lock_header_does_not_leak_local_paths() -> None:
    """公开锁文件不能包含生成者本机绝对路径。"""
    text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    header = "\n".join(text.splitlines()[:4])

    assert "/Users/" not in header
    assert "-o requirements.lock requirements.in" in header


def test_bl117_a1_local_packages_are_not_locked() -> None:
    """本地源码包不能进入第三方锁文件，Docker 中必须由源码安装。"""
    locked = {canonicalize_name(block.split("==", 1)[0].strip()) for block in _locked_blocks()}

    assert not (locked & LOCAL_PACKAGES)


def test_bl117_a2_build_tools_are_locked_and_build_isolation_disabled() -> None:
    """本地 editable 构建也不应动态下载 setuptools / wheel。"""
    locked = {canonicalize_name(block.split("==", 1)[0].strip()) for block in _locked_blocks()}
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert {"setuptools", "wheel"} <= locked
    assert "pip install --no-deps --no-build-isolation -e ./packages/core" in dockerfile
    assert "pip install --no-deps --no-build-isolation -e ." in dockerfile


def test_bl117_a2_a3_e3_docker_uses_hash_locked_dependencies() -> None:
    """Docker 禁止第三方依赖动态解析，并配置弱网重试。"""
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "PIP_DEFAULT_TIMEOUT=120" in dockerfile
    assert "PIP_RETRIES=10" in dockerfile
    assert "--mount=type=cache,target=/root/.cache/pip" in dockerfile
    assert "pip install --require-hashes -r requirements.lock" in dockerfile
    assert "pip install --no-deps --no-build-isolation -e ./packages/core" in dockerfile
    assert "pip install --no-deps --no-build-isolation -e ." in dockerfile
