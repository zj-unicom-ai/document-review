# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-104：多租户菜单级 RBAC 表与存量角色迁移。

Revision ID: 0005_multi_tenant_rbac
Revises: 0004_drop_regression
Create Date: 2026-10-15
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import select, table, column

revision = "0005_multi_tenant_rbac"
down_revision = "0004_drop_regression"
branch_labels = None
depends_on = None

_SUPERADMIN_TENANT = "superadmin"


def _rbac_tables():
    """迁移用轻量表对象，避免把新模型提前挂到 Alembic 基线 metadata。"""
    roles = table(
        "roles",
        column("id", sa.BigInteger),
        column("tenant_code", sa.String),
        column("code", sa.String),
        column("name", sa.String),
        column("description", sa.String),
        column("is_system", sa.Boolean),
        column("status", sa.String),
        column("created_by", sa.String),
        column("updated_by", sa.String),
    )
    user_roles = table(
        "user_roles",
        column("user_id", sa.BigInteger),
        column("role_id", sa.BigInteger),
    )
    role_menus = table(
        "role_menus",
        column("role_id", sa.BigInteger),
        column("menu_code", sa.String),
    )
    return roles, user_roles, role_menus


def _builtin_roles(tenant_code: str) -> list[dict[str, object]]:
    if tenant_code == _SUPERADMIN_TENANT:
        return [
            {
                "tenant_code": tenant_code,
                "code": "super_admin",
                "name": "平台超级管理员",
                "description": "平台内置角色，拥有全部菜单权限。",
                "is_system": True,
            }
        ]
    return [
        {
            "tenant_code": tenant_code,
            "code": "tenant_admin",
            "name": "租户管理员",
            "description": "租户内置角色，拥有本租户全部可用菜单。",
            "is_system": True,
        },
        {
            "tenant_code": tenant_code,
            "code": "member",
            "name": "普通用户",
            "description": "租户内置角色，默认只能使用文档审查。",
            "is_system": True,
        },
    ]


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column(
            "id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True
        ),
        sa.Column("tenant_code", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["tenant_code"], ["tenants.code"], name="fk_roles_tenant_code"),
        sa.UniqueConstraint("tenant_code", "code", name="uq_roles_tenant_code_code"),
    )
    op.create_index("ix_roles_tenant_code", "roles", ["tenant_code"])
    op.create_table(
        "user_roles",
        sa.Column(
            "user_id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "role_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_table(
        "role_menus",
        sa.Column(
            "role_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            sa.ForeignKey("roles.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("menu_code", sa.String(length=64), primary_key=True),
    )

    conn = op.get_bind()
    tenants = table(
        "tenants",
        column("code", sa.String),
        column("is_deleted", sa.Boolean),
    )
    users = table(
        "users",
        column("id", sa.BigInteger),
        column("tenant_code", sa.String),
        column("role", sa.String),
        column("is_deleted", sa.Boolean),
    )
    roles, user_roles, _ = _rbac_tables()

    tenant_codes = conn.execute(select(tenants.c.code)).scalars().all()
    role_ids: dict[tuple[str, str], int] = {}
    for tenant_code in tenant_codes:
        for values in _builtin_roles(str(tenant_code)):
            conn.execute(
                roles.insert().values(
                    **values,
                    status="active",
                    created_by="migration",
                    updated_by="migration",
                )
            )
            role_id = conn.execute(
                select(roles.c.id).where(
                    roles.c.tenant_code == tenant_code,
                    roles.c.code == values["code"],
                )
            ).scalar_one()
            role_ids[(str(tenant_code), str(values["code"]))] = int(role_id)

    user_rows = conn.execute(
        select(users.c.id, users.c.tenant_code, users.c.role)
    ).all()
    for user_id, tenant_code, legacy_role in user_rows:
        if tenant_code == _SUPERADMIN_TENANT:
            role_code = "super_admin"
        elif legacy_role == "tenant_admin":
            role_code = "tenant_admin"
        else:
            role_code = "member"
        conn.execute(
            user_roles.insert().values(
                user_id=user_id,
                role_id=role_ids[(str(tenant_code), role_code)],
            )
        )

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_role")
        batch_op.drop_column("role")


def downgrade() -> None:
    roles, user_roles, _ = _rbac_tables()
    users = table(
        "users",
        column("id", sa.BigInteger),
        column("tenant_code", sa.String),
        column("role", sa.String),
    )
    role = table(
        "roles",
        column("id", sa.BigInteger),
        column("code", sa.String),
    )

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(length=32), nullable=False, server_default="member")
        )
        batch_op.create_index("ix_users_role", columns=["role"])

    conn = op.get_bind()
    rows = conn.execute(
        select(users.c.id, role.c.code).select_from(
            users.join(user_roles, users.c.id == user_roles.c.user_id)
            .join(role, user_roles.c.role_id == role.c.id)
        )
    ).all()
    # 多角色回滚到单角色字段时按内置角色优先级取值，避免依赖数据库返回顺序。
    legacy_priority = {"super_admin": 0, "tenant_admin": 1, "member": 2}
    role_by_user: dict[object, tuple[int, str]] = {}
    for user_id, role_code in rows:
        current = role_by_user.get(user_id)
        priority = legacy_priority.get(str(role_code), 99)
        if current is None or priority < current[0]:
            role_by_user[user_id] = (priority, str(role_code))
    for user_id, (_, role_code) in role_by_user.items():
        conn.execute(users.update().where(users.c.id == user_id).values(role=role_code))

    op.drop_table("role_menus")
    op.drop_table("user_roles")
    op.drop_index("ix_roles_tenant_code", table_name="roles")
    op.drop_table("roles")
