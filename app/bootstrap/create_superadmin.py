# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""为 migration 创建的 admin 账号设置初始密码。"""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from getpass import getpass

from app.core.db import get_sessionmaker
from app.services.user import UserService

MIN_PASSWORD_LENGTH = 12


async def run(
    session,
    password_provider: Callable[[], str | Awaitable[str]],
) -> int:
    """在给定会话中设置超管密码；密码来源由入口注入，便于测试。"""
    provided = password_provider()
    if isinstance(provided, Awaitable):
        provided = await provided
    password = str(provided)
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"超管密码至少需要 {MIN_PASSWORD_LENGTH} 位", file=sys.stderr)
        return 2
    user = await UserService(session).set_superadmin_password(password)
    print(f"已设置超管账号 {user.username} 的密码")
    return 0


def _prompt_password() -> str:
    first = getpass("请输入超管初始密码（至少 12 位）：")
    second = getpass("请再次输入超管初始密码：")
    if first != second:
        raise ValueError("两次输入的密码不一致")
    return first


async def main() -> int:
    env_password = os.environ.get("SUPERADMIN_INITIAL_PASSWORD")
    sm = get_sessionmaker()
    async with sm() as session:
        return await run(
            session, (lambda: env_password) if env_password is not None else _prompt_password
        )


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
