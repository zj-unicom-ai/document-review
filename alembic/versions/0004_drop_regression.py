# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-067：删除回归验证三张表。

Revision ID: 0004_drop_regression
Revises: 0003_auth_superadmin
Create Date: 2026-10-09

功能随 BL-067 彻底下线；downgrade 可重建空表结构（不恢复数据）。
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_drop_regression"
down_revision = "0003_auth_superadmin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 依赖顺序：先子表后主表；IF EXISTS 保证新库（未建过这些表）幂等
    op.execute("DROP TABLE IF EXISTS regression_runs")
    op.execute("DROP TABLE IF EXISTS regression_cases")
    op.execute("DROP TABLE IF EXISTS regression_suites")


def downgrade() -> None:
    # 结构回滚：与删除前模型一致，便于必要时恢复功能重新开发
    op.create_table(
        "regression_suites",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False, server_default="", index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("bound_rule_ids", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column("updated_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "regression_cases",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("suite_id", sa.Integer(), sa.ForeignKey("regression_suites.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "regression_runs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("suite_id", sa.Integer(), sa.ForeignKey("regression_suites.id"), nullable=False, index=True),
        sa.Column("rule_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("diff_report", sa.JSON(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
