# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-007 Docker 启动链路与部署配置生成测试。"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from scripts.setup_docker import write_docker_env

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _write_fake_commands(binary_dir: Path, log_path: Path, command: str) -> None:
    """生成记录调用的 fake 命令，避免测试触达数据库或启动服务。"""
    script = binary_dir / command
    script.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                f'printf "%s\\n" "$*" >> "{log_path}"',
                f'printf "%s\\n" "SUPERADMIN_INITIAL_PASSWORD=$SUPERADMIN_INITIAL_PASSWORD" >> "{log_path}"',
                "exit 0",
            ]
        ),
        encoding="utf-8",
    )
    script.chmod(0o755)


def _run_entrypoint(
    tmp_path: Path, env_overrides: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    binary_dir = tmp_path / "bin"
    log_path = tmp_path / "commands.log"
    binary_dir.mkdir()
    for command in ("alembic", "python", "uvicorn"):
        _write_fake_commands(binary_dir, log_path, command)

    env = {
        "PATH": f"{binary_dir}{os.pathsep}{os.environ['PATH']}",
        "APP_ENV": "production",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "RUN_PLATFORM_SEED": "true",
        "AUTH_SECRET_KEY": "a-runtime-auth-secret",
        "SUPERADMIN_INITIAL_PASSWORD": "Changeme@2026",
        **env_overrides,
    }
    return subprocess.run(
        [str(PROJECT_ROOT / "deploy" / "backend-entrypoint.sh")],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_bl007_a6_entrypoint_runs_idempotent_bootstrap_after_seed(tmp_path: Path) -> None:
    result = _run_entrypoint(tmp_path, {})

    assert result.returncode == 0, result.stderr
    lines = (tmp_path / "commands.log").read_text(encoding="utf-8").splitlines()
    assert "upgrade head" in lines
    assert "-m app.seed.load_seed" in lines
    assert "-m app.bootstrap.initialize_superadmin" in lines
    assert (
        lines[lines.index("-m app.bootstrap.initialize_superadmin") + 1]
        == "SUPERADMIN_INITIAL_PASSWORD=Changeme@2026"
    )
    assert lines.index("-m app.seed.load_seed") < lines.index(
        "-m app.bootstrap.initialize_superadmin"
    )


def test_bl007_e1_entrypoint_rejects_missing_auth_secret_in_production(tmp_path: Path) -> None:
    result = _run_entrypoint(tmp_path, {"AUTH_SECRET_KEY": ""})

    assert result.returncode != 0
    assert "AUTH_SECRET_KEY" in result.stderr
    assert not (tmp_path / "commands.log").exists()


def test_bl007_setup_script_generates_local_docker_env(tmp_path: Path) -> None:
    example = tmp_path / ".env.docker.example"
    example.write_text(
        "\n".join(
            [
                "MYSQL_ROOT_PASSWORD=change-me-database-password",
                "MYSQL_PASSWORD=change-me-database-password",
                "AUTH_SECRET_KEY=change-me-auth-secret-key",
                "SUPERADMIN_INITIAL_PASSWORD=Changeme@2026",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    target = tmp_path / ".env.docker"
    values = iter(["root-secret", "app-secret", "auth-secret"])

    write_docker_env(example, target, lambda: next(values))

    text = target.read_text(encoding="utf-8")
    assert "MYSQL_ROOT_PASSWORD=root-secret" in text
    assert "MYSQL_PASSWORD=app-secret" in text
    assert "AUTH_SECRET_KEY=auth-secret" in text
    assert "SUPERADMIN_INITIAL_PASSWORD=Changeme@2026" in text
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_bl007_e1_setup_script_does_not_overwrite_existing_env(tmp_path: Path) -> None:
    example = tmp_path / ".env.docker.example"
    example.write_text("MYSQL_PASSWORD=change-me\n", encoding="utf-8")
    target = tmp_path / ".env.docker"
    target.write_text("MYSQL_PASSWORD=keep-me\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_docker_env(example, target, lambda: "generated-secret")
