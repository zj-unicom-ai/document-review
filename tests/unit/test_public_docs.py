# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-118 公开文档边界与内容契约测试。"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PUBLIC_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "LICENSE",
    "NOTICE.md",
    "CHANGELOG.md",
    "docs/architecture.md",
    "docs/configuration.md",
    "docs/deployment.md",
    "docs/developer-guide.md",
    "docs/operations.md",
    "docs/security.md",
    "docs/user-guide.md",
)

# 用 Unicode 转义维护禁止词，避免测试文件本身扩散敏感明文。
FORBIDDEN_PUBLIC_PATTERNS = (
    r"\u62a5\u544a\u6d4b\u8bd5\u6837\u4f8b",
    r"\u6e29\u5dde",
    r"\u676d\u5dde",
    r"\u8862\u5dde",
    r"\u4e50\u6e05",
    r"\u745e\u5b89",
    r"\u82cd\u5357",
    r"safety-insurance-b[a-z]+end",
    r"\u5171\u4eab MySQL",
    r"\u5185\u90e8\u9a8c\u8bc1",
    r"\u57fa\u51c6\u89c4\u5219",
    r"git\.fubao[0-9]+\.cn",
    r"run_sample_reviews",
    r"sample_rules",
)


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_bl118_a1_required_public_docs_exist() -> None:
    missing = [relative for relative in PUBLIC_DOCS if not (ROOT / relative).is_file()]

    assert not missing


def test_bl118_a2_readme_covers_quickstart_account_mock_and_license() -> None:
    text = _read("README.md")

    assert "## 快速开始" in text
    assert "python scripts/setup_docker.py" in text
    assert "docker compose --env-file .env.docker up -d --build" in text
    assert "Changeme@2026" in text
    assert "--profile mocks" in text
    assert "MIT License" in text


def test_bl127_a2_readme_covers_release_boundary_and_roadmap() -> None:
    text = _read("README.md")

    assert "## 当前边界" in text
    assert "## Roadmap" in text
    assert "仅发布源码" in text
    assert "不发布官方 Docker 镜像" in text
    assert "反向代理" in text
    assert "登录限速" in text
    assert "外部资源适配器" in text


def test_bl127_a1_changelog_covers_first_release() -> None:
    text = _read("CHANGELOG.md")

    assert "## 0.1.0" in text
    assert "2026-10-22" in text
    assert "多租户" in text
    assert "Docker Compose" in text
    assert "仅发布源码" in text
    assert "PyMuPDF" in text
    assert "AGPL-3.0" in text
    assert "Artifex Commercial License" in text


def test_bl118_a3_configuration_covers_required_sections() -> None:
    text = _read("docs/configuration.md")
    required_variables = (
        "AUTH_SECRET_KEY",
        "SUPERADMIN_INITIAL_PASSWORD",
        "DB_HOST",
        "REDIS_HOST",
        "LLM_BASE_URL",
        "LLM_TEXT_BASE_URL",
        "MINERU_PROVIDER",
        "MINERU_PRIVATE_API_SERVER",
        "STORAGE_ROOT",
        "AGENT_API_KEY",
    )

    assert "## 认证" in text
    assert "## 数据库" in text
    assert "## Redis" in text
    assert "## LLM" in text
    assert "## MinerU" in text
    assert "## 存储" in text
    assert all(variable in text for variable in required_variables)


def test_bl118_a4_user_guide_covers_end_to_end_pages() -> None:
    text = _read("docs/user-guide.md")

    assert "登录" in text
    assert "选择租户" in text
    assert "概念" in text
    assert "规则" in text
    assert "规则集" in text
    assert "上传 PDF" in text
    assert "审查结果" in text
    assert "批注 PDF" in text


def test_bl127_a3_user_guide_distinguishes_rule_api_and_template_ui_trial() -> None:
    text = _read("docs/user-guide.md")

    assert "保存前可用样例 PDF 试跑" not in text
    assert "规则试跑 API" in text
    assert "模板管理" in text
    assert "样例试跑" in text


def test_bl127_a4_security_documents_runtime_boundaries() -> None:
    text = _read("docs/security.md")

    assert "未内置登录限速" in text
    assert "账号锁定" in text
    assert "反向代理" in text
    assert "body size" in text
    assert "/docs" in text
    assert "HTTPS" in text


def test_bl118_a5_developer_guide_covers_verification_commands() -> None:
    text = _read("docs/developer-guide.md")

    assert "pytest" in text
    assert "ruff check ." in text
    assert "ruff format --check ." in text
    assert "npm run typecheck" in text
    assert "npm run test -- --run" in text
    assert "npm run build" in text
    assert "python scripts/compile_python_lock.py --check" in text


def test_bl118_e1_public_docs_do_not_reference_private_context() -> None:
    hits: list[str] = []
    for relative in PUBLIC_DOCS:
        text = _read(relative)
        for pattern in FORBIDDEN_PUBLIC_PATTERNS:
            if re.search(pattern, text):
                hits.append(f"{relative}: forbidden context {pattern}")

    assert not hits


def test_bl118_e2_repository_relative_links_resolve() -> None:
    pattern = re.compile(r"\[[^\]]+\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
    broken: list[str] = []

    for relative in PUBLIC_DOCS:
        path = ROOT / relative
        for target in pattern.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            target_path = (path.parent / target).resolve()
            if not target_path.exists():
                broken.append(f"{relative}: {target}")

    assert not broken
