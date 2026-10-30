# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""create auth users and reserved superadmin tenant

Revision ID: 0003_auth_superadmin
Revises: 0002_cls_tenant_owned
Create Date: 2026-09-28

超管租户通过 migration 创建；admin 初始不设置可用密码。
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import delete, select

from alembic import op

revision = "0003_auth_superadmin"
down_revision = "0002_cls_tenant_owned"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("tenant_code", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
        ),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["tenant_code"], ["tenants.code"], name="fk_users_tenant_code"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_tenant_code", "users", ["tenant_code"])
    op.create_index("ix_users_role", "users", ["role"])

    conn = op.get_bind()
    tenants = sa.table(
        "tenants",
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("status", sa.String),
        sa.column("contact", sa.String),
        sa.column("note", sa.String),
        sa.column("created_by", sa.String),
        sa.column("updated_by", sa.String),
    )
    users = sa.table(
        "users",
        sa.column("id", sa.BigInteger),
        sa.column("tenant_code", sa.String),
        sa.column("username", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("display_name", sa.String),
        sa.column("role", sa.String),
        sa.column("status", sa.String),
        sa.column("created_by", sa.String),
        sa.column("updated_by", sa.String),
    )

    tenant_exists = conn.execute(
        select(tenants.c.code).where(tenants.c.code == "superadmin")
    ).scalar_one_or_none()
    if tenant_exists is None:
        conn.execute(
            tenants.insert().values(
                code="superadmin",
                name="平台超级管理员",
                status="active",
                contact=None,
                note="系统保留租户；只承载超管账号，不作为业务数据租户。",
                created_by="migration",
                updated_by="migration",
            )
        )

    admin_exists = conn.execute(
        select(users.c.id).where(users.c.username == "admin")
    ).scalar_one_or_none()
    if admin_exists is None:
        conn.execute(
            users.insert().values(
                tenant_code="superadmin",
                username="admin",
                password_hash="",
                display_name="平台超级管理员",
                role="super_admin",
                status="active",
                created_by="migration",
                updated_by="migration",
            )
        )


def downgrade() -> None:
    conn = op.get_bind()
    users = sa.table("users", sa.column("username", sa.String))
    tenants = sa.table("tenants", sa.column("code", sa.String))
    conn.execute(delete(users).where(users.c.username == "admin"))
    conn.execute(delete(tenants).where(tenants.c.code == "superadmin"))
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_tenant_code", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
