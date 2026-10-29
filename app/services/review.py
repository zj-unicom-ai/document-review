# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""审查 run 的租户读写与上传文件落盘。"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.storage import storage_display_path, tenant_storage_path
from app.models.review_run import ReviewRun


class ReviewService:
    """ReviewRun 表的服务边界；跨租户读取统一返回 404。"""

    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def create_run(
        self,
        file_name: str,
        file_bytes: bytes,
        *,
        created_by: str = "api",
    ) -> ReviewRun:
        """保存上传文件并创建 pending run。"""
        safe_name = Path(file_name).name
        if not safe_name or not file_bytes:
            raise ValidationError("上传文件不能为空")
        digest = hashlib.sha256(file_bytes).hexdigest()
        path = tenant_storage_path(
            self.tenant_id,
            "uploads",
            uuid.uuid4().hex,
            safe_name,
        )
        await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, file_bytes)
        run = ReviewRun(
            tenant_id=self.tenant_id,
            file_name=safe_name,
            file_sha256=digest,
            file_path=storage_display_path(path),
            file_size=len(file_bytes),
            status="pending",
            created_by=created_by,
        )
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get(self, run_id: int) -> ReviewRun:
        run = (
            await self.session.execute(
                select(ReviewRun).where(
                    ReviewRun.id == run_id,
                    ReviewRun.tenant_id == self.tenant_id,
                    ReviewRun.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if run is None:
            raise NotFoundError(f"review run id={run_id} not found")
        return run

    async def list_runs(self, *, page: int, page_size: int) -> tuple[list[ReviewRun], int]:
        """分页列出当前租户的审查记录，最新在前。"""
        base = select(ReviewRun).where(
            ReviewRun.tenant_id == self.tenant_id,
            ReviewRun.is_deleted.is_(False),
        )
        total = (
            await self.session.execute(select(func.count()).select_from(base.subquery()))
        ).scalar_one()
        rows = (
            (
                await self.session.execute(
                    base.order_by(ReviewRun.id.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

    async def delete_run(self, run_id: int) -> None:
        """软删除审查记录；物理文件保留以支持后续审计恢复。"""
        run = await self.get(run_id)
        run.is_deleted = True
        await self.session.commit()
