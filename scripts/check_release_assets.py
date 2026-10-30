# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""开源发布资产检查：拦截业务素材、样例数据和常见真实凭据。"""

from __future__ import annotations

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

PRIVATE_FORBIDDEN_DIR = "\u62a5\u544a\u6d4b\u8bd5\u6837\u4f8b"
PRIVATE_CONTEXT_MARKERS = (
    PRIVATE_FORBIDDEN_DIR,
    "\u8054\u901a\uff08\u6d59\u6c5f\uff09\u4ea7\u4e1a\u4e92\u8054\u7f51\u6709\u9650\u516c\u53f8",
    "\u5185\u90e8\u9a8c\u8bc1",
    "\u5185\u90e8\u7d20\u6750",
    "\u6d4b\u8bd5\u57fa\u51c6",
    "\u670d\u52a1\u62a5\u544a",
    "\u5171\u4eab MySQL",
    "\u5b89\u8d23\u9669",
    "\u6e29\u5dde",
    "\u676d\u5dde",
    "\u8862\u5dde",
    "\u4e50\u6e05",
    "\u745e\u5b89",
    "\u82cd\u5357",
)
FORBIDDEN_PATHS = {
    PRIVATE_FORBIDDEN_DIR,
    "app/seed/data/rules.json",
    "app/seed/data/rule_sets.json",
    "app/seed/sample_rules.py",
    "scripts/run_sample_reviews.py",
    ".env",
}

SECRET_MARKERS = (
    "\u0042EGIN PRIVATE \u004bEY",
    "\u0042EGIN RSA PRIVATE \u004bEY",
    "\u0042EGIN OPENSSH PRIVATE \u004bEY",
    "s\u006b-",
)

ENV_ASSIGNMENT = re.compile(
    r"^\s*(?:export\s+)?(?P<name>[A-Z_][A-Z0-9_]*)(?:\[[^]]+\])?\s*=",
)
CREDENTIAL_NAME = re.compile(r"(?:PASSWORD|API_KEY|SECRET_KEY|TOKEN)$")

ALLOWED_TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".example",
    ".sh",
}
ALLOWED_TEXT_NAMES = {".dockerignore", ".gitignore", ".env.example", ".env.docker.example"}
GENERATED_DIRECTORY_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
}

COPYRIGHT_OWNER = "Copyright (c) 2026 ZJ-Unicom-AI"


def _is_secret(line: str) -> bool:
    """只把疑似真实密钥视为泄漏；占位值和空值不阻塞发布检查。"""
    lowered = line.lower()
    if any(marker.lower() in lowered for marker in SECRET_MARKERS):
        return "placeholder" not in lowered and "change-me" not in lowered
    assignment = ENV_ASSIGNMENT.match(line)
    if assignment is None or CREDENTIAL_NAME.search(assignment.group("name")) is None:
        return False
    value = line.split("=", 1)[1].strip().strip("'\"").rstrip("\\").strip()
    return bool(value) and value.lower() not in {
        "change-me-database-password",
        "change-me-auth-secret-key",
        "changeme@2026",
        "mock-key",
        "<openssl rand -base64 48>",
        "${superadmin_initial_password:-changeme@2026}",
        "change-me",
        "placeholder",
        "sk-placeholder",
        "test",
        "not-set",
        "null",
    }


def _is_internal_context(line: str) -> bool:
    """识别不应进入公开发行物的内部研发与业务语境。"""
    return any(marker in line for marker in PRIVATE_CONTEXT_MARKERS)


def _git_ignored_generated_paths(root: Path) -> set[str]:
    """读取 Git 明确忽略的本地生成目录；非 Git 归档不适用该豁免。"""
    if not (root / ".git").exists():
        return set()
    tracked_result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    tracked = {
        raw_path.decode("utf-8", errors="replace")
        for raw_path in tracked_result.stdout.split(b"\0")
        if raw_path
    }
    result = subprocess.run(
        ["git", "ls-files", "--others", "--directory", "--ignored", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    ignored: set[str] = set()
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8", errors="replace").rstrip("/")
        if not relative:
            continue
        if relative in tracked or any(path.startswith(f"{relative}/") for path in tracked):
            continue
        if any(part in GENERATED_DIRECTORY_NAMES for part in Path(relative).parts):
            ignored.add(relative)
    return ignored


def check_release_root(root: Path) -> list[str]:
    """检查一个发布归档解包目录，返回阻断发布的问题列表。"""
    if not root.is_dir():
        return [f"发布目录不存在: {root}"]

    problems = _check_legal_baseline(root)
    ignored_generated = _git_ignored_generated_paths(root)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        forbidden = relative in FORBIDDEN_PATHS or any(
            relative == f"{forbidden}/" or relative.startswith(f"{forbidden}/")
            for forbidden in FORBIDDEN_PATHS
        )
        if forbidden or path.name == ".env":
            problems.append(f"禁止发布业务 / 敏感文件: {relative}")
            continue
        if relative in ignored_generated or any(
            relative.startswith(f"{prefix}/") for prefix in ignored_generated
        ):
            continue
        if path.suffix.lower() not in ALLOWED_TEXT_SUFFIXES and path.name not in ALLOWED_TEXT_NAMES:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(lines, 1):
            if _is_internal_context(line):
                problems.append(f"内部语境: {relative}:{number}")
                break
            if _is_secret(line):
                problems.append(f"疑似真实凭据: {relative}:{number}")
                break
    return sorted(set(problems))


def check_git_history(root: Path) -> list[str]:
    """扫描所有 Git 提交树中的禁止路径和疑似真实凭据。"""
    if not (root / ".git").exists():
        return [f"不是 Git 仓库: {root}"]
    commits = subprocess.run(
        ["git", "rev-list", "--all"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    if not commits:
        return ["Git 仓库没有任何提交"]

    problems: list[str] = []
    history_secret_pattern = (
        "\u0042EGIN (RSA |OPENSSH |EC )?PRIVATE \u004bEY|s\u006b-"
        r"|[A-Za-z_]*(KEY|TOKEN|PASSWORD)[A-Za-z_]*\s*="
    )
    for commit in commits:
        paths = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "-z", commit],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout.split(b"\0")
        for raw_path in paths:
            if not raw_path:
                continue
            path = raw_path.decode("utf-8", errors="replace")
            if (
                path in FORBIDDEN_PATHS
                or Path(path).name == ".env"
                or path.startswith(f"{PRIVATE_FORBIDDEN_DIR}/")
            ):
                problems.append(f"历史提交 {commit} 禁止路径: {path}")

        grep = subprocess.run(
            [
                "git",
                "grep",
                "-I",
                "-n",
                "-i",
                "-E",
                history_secret_pattern,
                commit,
                "--",
                ".",
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
        for line in grep.stdout.splitlines():
            try:
                _commit, path, number, content = line.split(":", 3)
            except ValueError:
                continue
            if _is_secret(content):
                problems.append(f"历史提交 {commit} 疑似真实凭据: {path}:{number}")
    return sorted(set(problems))


def _check_legal_baseline(root: Path) -> list[str]:
    """校验 MIT、包元数据与关键第三方授权风险说明。"""
    problems: list[str] = []

    license_path = root / "LICENSE"
    license_text = license_path.read_text(encoding="utf-8") if license_path.is_file() else ""
    if not license_path.is_file():
        problems.append("缺少 LICENSE")
    elif "MIT License" not in license_text or COPYRIGHT_OWNER not in license_text:
        problems.append("LICENSE 版权主体或 MIT 文本不正确")

    notice_path = root / "NOTICE.md"
    notice_text = notice_path.read_text(encoding="utf-8") if notice_path.is_file() else ""
    if not notice_path.is_file():
        problems.append("缺少 NOTICE.md")
    elif not all(
        marker in notice_text for marker in ("PyMuPDF", "AGPL-3.0", "Artifex Commercial License")
    ):
        problems.append("NOTICE.md 必须声明 PyMuPDF 的 AGPL-3.0 / Artifex Commercial License 风险")

    for relative in ("pyproject.toml", "packages/core/pyproject.toml"):
        path = root / relative
        try:
            metadata = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
            license_value = metadata.get("license", {})
            declared_license = (
                license_value.get("text") if isinstance(license_value, dict) else license_value
            )
        except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
            problems.append(f"{relative} 缺少 project.license")
            continue
        if declared_license != "MIT":
            problems.append(f"{relative} license 必须声明为 MIT")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="检查开源发布包是否包含业务素材或凭据")
    parser.add_argument("roots", nargs="*", type=Path, help="发布归档解包目录")
    parser.add_argument("--scan-history", action="store_true", help="扫描 Git 全部提交树")
    args = parser.parse_args()

    if args.scan_history:
        if len(args.roots) != 1:
            parser.error("--scan-history 只能指定一个 Git 仓库")
        args.roots[0].exists() or parser.error("Git 仓库不存在")
        problems = check_git_history(args.roots[0])
    else:
        if not args.roots:
            parser.error("至少指定一个发布目录")
        problems = []
        for root in args.roots:
            problems.extend(check_release_root(root))

    if problems:
        print("发布资产检查失败：")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("发布资产检查通过：未发现禁止文件或真实凭据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
