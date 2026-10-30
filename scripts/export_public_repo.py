# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""按 allowlist 导出干净公开仓库候选。"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

ROOT_FILES = {
    "CHANGELOG.md",
    ".dockerignore",
    ".env.docker.example",
    ".env.example",
    ".gitignore",
    "CONTRIBUTING.md",
    "Dockerfile",
    "LICENSE",
    "NOTICE.md",
    "README.md",
    "SECURITY.md",
    "alembic.ini",
    "docker-compose.yml",
    "pyproject.toml",
    "requirements.in",
    "requirements.lock",
}

PUBLIC_DIRECTORIES = {
    "alembic/",
    "app/",
    "deploy/",
    "examples/",
    "packages/core/",
    "sbom/",
    "web/",
}

PUBLIC_SCRIPTS = {
    "scripts/check_release_assets.py",
    "scripts/compile_python_lock.py",
    "scripts/export_public_repo.py",
    "scripts/setup_docker.py",
}

PUBLIC_DOCS = {
    "docs/architecture.md",
    "docs/configuration.md",
    "docs/deployment.md",
    "docs/developer-guide.md",
    "docs/operations.md",
    "docs/security.md",
    "docs/user-guide.md",
}

PUBLIC_TESTS = {
    "tests/conftest.py",
    "tests/unit/bootstrap/test_initialize_superadmin.py",
    "tests/unit/engine/test_generic_item_list.py",
    "tests/unit/test_deployment_bootstrap.py",
    "tests/unit/test_mock_mineru.py",
    "tests/unit/test_mysql_runtime_dependencies.py",
    "tests/unit/test_operations_backup_docs.py",
    "tests/unit/test_public_docs.py",
    "tests/unit/test_public_github_config.py",
    "tests/unit/test_open_source_security_remediation.py",
    "tests/unit/test_python_lock.py",
    "tests/unit/test_web_dependency_security.py",
}

PUBLIC_GITHUB_FILES = {
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
}

# 使用转义避免公开脚本继续扩散私有样例目录明文。
PRIVATE_SAMPLE_DIR = "\u62a5\u544a\u6d4b\u8bd5\u6837\u4f8b"
FORBIDDEN_PREFIXES = (
    f"{PRIVATE_SAMPLE_DIR}/",
    ".cursor/",
    "docs/lifecycle/",
    "docs/product/",
    "docs/superpowers/",
)
FORBIDDEN_PATHS = {
    "app/seed/data/__init__.py",
    "app/seed/data/classifications.json",
    "app/seed/data/concepts.json",
    "app/seed/data/rule_sets.json",
    "app/seed/data/rules.json",
    "app/seed/sample_rules.py",
    "scripts/run_sample_reviews.py",
    "AGENTS.md",
    ".github/copilot-instructions.md",
    "CLAUDE.md",
    "GEMINI.md",
    "docs/embedding.md",
    "docs/evaluations.md",
    "docs/open-source-checklist.md",
    "docs/rules-catalog.md",
    "docs/spec.md",
}


def _normalized(relative: str | Path) -> str:
    path = Path(relative).as_posix()
    return path[2:] if path.startswith("./") else path


def _is_allowed(relative: str | Path) -> bool:
    """判断 Git 跟踪路径是否允许进入公开导出。"""
    path = _normalized(relative)
    if path in FORBIDDEN_PATHS or path.startswith(FORBIDDEN_PREFIXES):
        return False
    if path.startswith("app/seed/data/"):
        return False
    if (
        path in ROOT_FILES
        or path in PUBLIC_GITHUB_FILES
        or path in PUBLIC_SCRIPTS
        or path in PUBLIC_DOCS
        or path in PUBLIC_TESTS
    ):
        return True
    return path.startswith(tuple(PUBLIC_DIRECTORIES))


def _tracked_files(source: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=source,
        check=True,
        capture_output=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _init_git(output: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=output, check=True)
    subprocess.run(["git", "config", "user.name", "document-review export"], cwd=output, check=True)
    subprocess.run(
        ["git", "config", "user.email", "opensource@example.com"], cwd=output, check=True
    )
    subprocess.run(["git", "add", "."], cwd=output, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "chore: initialize public source"],
        cwd=output,
        check=True,
    )


def export_public_repository(source: Path, output: Path, *, init_git: bool = False) -> list[str]:
    """导出 allowlist 文件并生成 manifest；输出目录必须不存在。"""
    if output.exists():
        raise FileExistsError(f"输出目录已存在: {output}")

    tracked = _tracked_files(source)
    selected = sorted(path for path in tracked if _is_allowed(path))
    if not selected:
        raise RuntimeError("公开 allowlist 未选中任何文件")

    output.mkdir(parents=True)
    copied: list[str] = []
    for relative in selected:
        source_path = source / relative
        target_path = output / relative
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied.append(relative)

    manifest = {
        "algorithm": "sha256",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip(),
        "files": {relative: _sha256(output / relative) for relative in copied},
    }
    (output / "PUBLIC_EXPORT_MANIFEST.json").write_text(
        __import__("json").dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if init_git:
        _init_git(output)
    return copied


def main() -> int:
    parser = argparse.ArgumentParser(description="导出干净公开仓库候选")
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, default=Path.cwd())
    parser.add_argument("--init-git", action="store_true", help="初始化单 commit 公开历史")
    args = parser.parse_args()
    files = export_public_repository(args.source, args.output, init_git=args.init_git)
    print(f"已导出 {len(files)} 个文件到 {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
