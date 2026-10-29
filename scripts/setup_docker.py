# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""生成 Docker Compose 本机配置，避免使用者手工编写密钥。"""

from __future__ import annotations

import argparse
import secrets
import stat
from collections.abc import Callable
from pathlib import Path

DEFAULT_SUPERADMIN_INITIAL_PASSWORD = "Changeme@2026"
GENERATED_KEYS = ("MYSQL_ROOT_PASSWORD", "MYSQL_PASSWORD", "AUTH_SECRET_KEY")


def render_docker_env(
    example_text: str,
    secret_factory: Callable[[], str],
    *,
    superadmin_initial_password: str = DEFAULT_SUPERADMIN_INITIAL_PASSWORD,
) -> str:
    """替换示例中的占位密钥，并固定写入平台超管初始密码。"""
    generated = {key: secret_factory() for key in GENERATED_KEYS}
    values = {**generated, "SUPERADMIN_INITIAL_PASSWORD": superadmin_initial_password}
    lines: list[str] = []
    seen: set[str] = set()
    for line in example_text.splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in values:
            lines.append(f"{key}={values[key]}")
            seen.add(key)
        else:
            lines.append(line)

    missing = [key for key in values if key not in seen]
    if missing:
        lines.extend(f"{key}={values[key]}" for key in missing)
    return "\n".join(lines) + "\n"


def write_docker_env(
    example: Path,
    target: Path,
    secret_factory: Callable[[], str] | None = None,
) -> None:
    """从模板生成 `.env.docker`；已有文件直接失败，防止覆盖本机密钥。"""
    if target.exists():
        raise FileExistsError(f"{target} 已存在；如需重新生成请先手动确认并删除")

    factory = secret_factory or (lambda: secrets.token_urlsafe(36))
    rendered = render_docker_env(example.read_text(encoding="utf-8"), factory)
    with target.open("x", encoding="utf-8") as file:
        file.write(rendered)
    target.chmod(stat.S_IRUSR | stat.S_IWUSR)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 document-review Docker 部署配置")
    parser.add_argument("--example", type=Path, default=Path(".env.docker.example"))
    parser.add_argument("--target", type=Path, default=Path(".env.docker"))
    args = parser.parse_args()

    write_docker_env(args.example, args.target)
    print(f"已生成 {args.target}（权限 0600）")
    print("平台超管：superadmin / admin / Changeme@2026")
    print("后续执行：docker compose --env-file .env.docker up -d --build")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
