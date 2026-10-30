# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""测试根 conftest：提供 SQLite in-memory async engine 与 session fixture。

所有集成测试（service / API）都走这一份 fixture。`function` scope 保证每个
用例一个独立 in-memory DB，事务回滚互不污染（E6 跨 fixture 隔离）。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models import Base


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """每次用例一个新 in-memory SQLite engine；用完 dispose 释放。"""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """依赖 engine 的 session；expire_on_commit=False 便于测试断言后访问字段。"""
    sm = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with sm() as s:
        yield s
