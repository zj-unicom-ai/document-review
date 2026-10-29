# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Docker 首次部署的平台超管幂等初始化命令。"""

from __future__ import annotations

import asyncio
import os
import sys

from app.core.db import dispose_engine, get_sessionmaker
from app.services.user import UserService

DEFAULT_SUPERADMIN_INITIAL_PASSWORD = "Changeme@2026"
MIN_PASSWORD_LENGTH = 12


def resolve_initial_password(env: dict[str, str]) -> str:
    """环境变量优先；未配置时使用开源部署约定的固定初始密码。"""
    return env.get("SUPERADMIN_INITIAL_PASSWORD") or DEFAULT_SUPERADMIN_INITIAL_PASSWORD


async def run(session, password: str) -> int:
    """按密码哈希是否为空决定初始化或跳过，避免容器重启覆盖密码。"""
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"超管密码至少需要 {MIN_PASSWORD_LENGTH} 位", file=sys.stderr)
        return 2

    user, initialized = await UserService(session).initialize_superadmin(password)
    action = "已初始化" if initialized else "已有密码，已跳过初始化"
    print(f"{action}超管账号 {user.username}")
    return 0


async def main() -> int:
    password = resolve_initial_password(dict(os.environ))
    sm = get_sessionmaker()
    try:
        async with sm() as session:
            return await run(session, password)
    finally:
        # 一次性命令退出前释放全局 engine，避免连接在事件循环关闭后被 GC 回收。
        await dispose_engine()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
