# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-124 公开 GitHub 工程配置契约测试。"""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.compile_python_lock import LOCK_FORK_STRATEGY, LOCK_PYTHON_VERSION
from scripts.export_public_repo import _is_allowed

ROOT = Path(__file__).resolve().parents[2]

PUBLIC_GITHUB_FILES = {
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
}


def _yaml(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _steps(workflow: dict, job: str) -> list[str]:
    commands: list[str] = []
    for step in workflow["jobs"][job]["steps"]:
        run = step.get("run")
        if run:
            commands.extend(command.strip() for command in run.splitlines() if command.strip())
    return commands


def _uses(workflow: dict, job: str) -> list[str]:
    return [step["uses"] for step in workflow["jobs"][job]["steps"] if "uses" in step]


def test_bl124_a1_public_github_files_are_defined_and_exportable() -> None:
    missing = [path for path in PUBLIC_GITHUB_FILES if not (ROOT / path).is_file()]

    assert not missing
    assert all(_is_allowed(path) for path in PUBLIC_GITHUB_FILES)
    assert not _is_allowed(".github/copilot-instructions.md")


def test_bl124_a2_backend_ci_checks_test_lint_and_lock() -> None:
    workflow = _yaml(".github/workflows/ci.yml")
    commands = _steps(workflow, "backend")

    assert "python -m pytest -q" in commands
    assert "ruff check ." in commands
    assert "ruff format --check ." in commands
    assert "python scripts/compile_python_lock.py --check" in commands


def test_bl132_a1_backend_ci_installs_uv_before_lock_check() -> None:
    workflow = _yaml(".github/workflows/ci.yml")
    uses = _uses(workflow, "backend")

    assert "astral-sh/setup-uv@v5" in uses


def test_bl132_a2_lock_resolution_is_deterministic() -> None:
    assert LOCK_FORK_STRATEGY == "requires-python"
    assert LOCK_PYTHON_VERSION == "3.12.16"


def test_bl132_a3_backend_uses_modern_python_for_runtime_checks() -> None:
    workflow = _yaml(".github/workflows/ci.yml")
    python_steps = [
        step
        for step in workflow["jobs"]["backend"]["steps"]
        if step.get("uses") == "actions/setup-python@v5"
    ]

    assert len(python_steps) == 1
    assert python_steps[0]["with"]["python-version"] == "3.12"


def test_bl124_a3_frontend_ci_checks_install_typecheck_build_and_audit() -> None:
    workflow = _yaml(".github/workflows/ci.yml")
    commands = _steps(workflow, "frontend")

    assert "npm ci" in commands
    assert "npm run test -- --run" in commands
    assert "npm run typecheck" in commands
    assert "npm run build" in commands
    assert "npm audit --audit-level=high" in commands


def test_bl124_a4_deployment_and_release_assets_are_checked() -> None:
    workflow = _yaml(".github/workflows/ci.yml")
    deployment = _steps(workflow, "deployment")
    release_assets = _steps(workflow, "release-assets")

    assert "docker compose --env-file .env.docker.example config --quiet" in deployment
    assert "python scripts/check_release_assets.py ." in release_assets
    assert "python scripts/check_release_assets.py --scan-history ." in release_assets


def test_bl124_e1_workflow_uses_least_privilege_and_safe_trigger() -> None:
    workflow = _yaml(".github/workflows/ci.yml")
    triggers = workflow.get("on", workflow.get(True))
    text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert workflow.get("permissions") == {"contents": "read"}
    assert set(triggers) == {"push", "pull_request"}
    assert "pull_request_target" not in text


def test_bl124_e2_templates_and_dependabot_are_public_safe() -> None:
    issue_text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in PUBLIC_GITHUB_FILES
        if path.startswith(".github/ISSUE_TEMPLATE/") and path.endswith(".md")
    )
    pr_text = (ROOT / ".github/PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
    dependabot = _yaml(".github/dependabot.yml")
    updates = {item["package-ecosystem"]: item for item in dependabot["updates"]}

    safety_terms = ("密钥", "私有文档", "内部系统")
    assert all(term in issue_text for term in safety_terms)
    assert all(term in pr_text for term in safety_terms)
    assert updates["pip"]["directory"] == "/"
    assert updates["npm"]["directory"] == "/web"
