# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""remove platform classification seed data

Revision ID: 0002_remove_platform_classifications
Revises: 0001_initial
Create Date: 2026-09-28

分类是租户业务数据；历史 seed 写入的平台行业分类统一软删除。
"""

from __future__ import annotations

from sqlalchemy import text

from alembic import op

revision = "0002_cls_tenant_owned"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

# 精确回滚标记：只恢复 upgrade 时被本次迁移标记的时间戳，避免恢复更早的历史软删行。
CLEANUP_MARK = "2026-09-28 16:31:00"


def upgrade() -> None:
    # 只隐藏升级时仍活跃的平台默认分类；保留物理数据和外键引用。
    op.execute(
        text(
            "UPDATE classifications SET is_deleted = 1, updated_at = :cleanup_mark "
            "WHERE tenant_id = '' AND is_deleted = 0"
        ).bindparams(cleanup_mark=CLEANUP_MARK)
    )


def downgrade() -> None:
    op.execute(
        text(
            "UPDATE classifications SET is_deleted = 0, updated_at = :cleanup_mark "
            "WHERE tenant_id = '' AND is_deleted = 1 AND updated_at = :cleanup_mark"
        ).bindparams(cleanup_mark=CLEANUP_MARK)
    )
