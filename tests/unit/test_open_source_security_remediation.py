"""BL-135 开源安全自查整改契约测试。"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

from app.core.config import Settings
from scripts.check_release_assets import check_release_root
from scripts.export_public_repo import _is_allowed

ROOT = Path(__file__).resolve().parents[2]
COMPANY_NAME = (
    "\u8054\u901a\uff08\u6d59\u6c5f\uff09\u4ea7\u4e1a\u4e92\u8054\u7f51\u6709\u9650\u516c\u53f8"
)
COPYRIGHT_LINE = "Copyright (c) 2026 Document Review Contributors"
LICENSE_COPYRIGHT_LINE = "Copyright (c) 2026 ZJ-Unicom-AI"


def _tracked_files() -> list[str]:
    return subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()


def _eligible_code_paths() -> list[str]:
    result = []
    for relative in _tracked_files():
        path = Path(relative)
        is_code_suffix = path.suffix in {".py", ".ts", ".tsx", ".sh", ".yaml", ".yml", ".mako"}
        if is_code_suffix or path.name == "Dockerfile":
            result.append(relative)
    return result


def test_bl135_a1_e1_company_name_is_removed_and_generic_copyright_is_used() -> None:
    hits: list[str] = []
    for relative in _tracked_files():
        path = ROOT / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if COMPANY_NAME in text:
            hits.append(relative)

    assert not hits
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    notice_text = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
    assert LICENSE_COPYRIGHT_LINE in license_text
    assert LICENSE_COPYRIGHT_LINE in notice_text


def test_bl135_a2_all_code_files_have_copyright_and_spdx_headers() -> None:
    paths = _eligible_code_paths()

    assert paths
    missing: list[str] = []
    for relative in paths:
        text = (ROOT / relative).read_text(encoding="utf-8")
        if COPYRIGHT_LINE not in text or "SPDX-License-Identifier: MIT" not in text:
            missing.append(relative)

    assert not missing


def test_bl135_a3_app_host_defaults_to_loopback_and_docker_overrides(monkeypatch) -> None:
    monkeypatch.delenv("APP_HOST", raising=False)
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))

    assert Settings(_env_file=None).app_host == "127.0.0.1"
    assert compose["services"]["api"]["environment"]["APP_HOST"] == "${APP_HOST:-0.0.0.0}"
    assert "APP_HOST=127.0.0.1" in (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "APP_HOST=0.0.0.0" in (ROOT / ".env.docker.example").read_text(encoding="utf-8")


def test_bl135_a4_public_frontend_has_no_legacy_report_context() -> None:
    frontend = ROOT / "web" / "src"
    hits = [
        path.relative_to(ROOT).as_posix()
        for path in frontend.rglob("*.tsx")
        if path.is_file() and "\u670d\u52a1\u62a5\u544a" in path.read_text(encoding="utf-8")
    ]

    assert not hits


def test_bl135_a5_readme_has_faq_and_examples_are_exportable() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required_examples = ("examples/README.md", "examples/generate_demo_pdf.py")

    assert "## 常见问题" in readme
    assert all((ROOT / path).is_file() for path in required_examples)
    assert all(_is_allowed(path) for path in required_examples)


def test_bl135_a5_example_generator_creates_synthetic_pdf(tmp_path: Path) -> None:
    output = tmp_path / "generic-demo.pdf"
    script = ROOT / "examples" / "generate_demo_pdf.py"

    subprocess.run([sys.executable, str(script), "--output", str(output)], check=True)

    assert output.is_file()
    assert output.read_bytes().startswith(b"%PDF-")
    assert "examples/generated/" in (ROOT / ".gitignore").read_text(encoding="utf-8")


def test_bl135_a6_public_sbom_covers_all_locked_dependencies() -> None:
    sbom = ROOT / "sbom" / "dependencies.csv"
    rows = list(csv.DictReader(sbom.open(encoding="utf-8", newline="")))
    python_lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    python_versions = set(re.findall(r"^([A-Za-z0-9_.-]+)==", python_lock, flags=re.MULTILINE))
    npm_lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
    npm_names = {
        item.get("name") or path.rsplit("node_modules/", 1)[-1]
        for path, item in npm_lock["packages"].items()
        if path and item.get("version")
    }
    by_ecosystem = {
        ecosystem: {row["name"] for row in rows if row["ecosystem"] == ecosystem}
        for ecosystem in ("PyPI", "npm")
    }

    assert sbom.is_file()
    assert python_versions <= by_ecosystem["PyPI"]
    assert npm_names <= by_ecosystem["npm"]
    assert all(row["version"] and row["license"] and row["source"] for row in rows)


def test_bl135_e1_release_checker_accepts_generic_copyright(tmp_path: Path) -> None:
    baseline = tmp_path / "public"
    baseline.mkdir()
    (baseline / "app").mkdir()
    (baseline / "packages" / "core").mkdir(parents=True)
    (baseline / "LICENSE").write_text(
        f"MIT License\n\n{LICENSE_COPYRIGHT_LINE}\n",
        encoding="utf-8",
    )
    (baseline / "NOTICE.md").write_text(
        "# Third-party notices\n\n- PyMuPDF: AGPL-3.0 or Artifex Commercial License.\n",
        encoding="utf-8",
    )
    for relative in ("pyproject.toml", "packages/core/pyproject.toml"):
        (baseline / relative).write_text(
            '[project]\nlicense = { text = "MIT" }\n',
            encoding="utf-8",
        )

    assert check_release_root(baseline) == []
