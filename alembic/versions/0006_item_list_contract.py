# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""BL-121 migrate legacy item list contract data.

Revision ID: 0006_item_list_contract
Revises: 0005_multi_tenant_rbac
Create Date: 2026-10-22
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy import column, select, table, update

revision = "0006_item_list_contract"
down_revision = "0005_multi_tenant_rbac"
branch_labels = None
depends_on = None

_FORWARD_TERMS = {
    "hazard_list": "item_list",
    "get_hazards": "get_list_items",
    "hazard_no": "item_no",
}
_REVERSE_TERMS = {value: key for key, value in _FORWARD_TERMS.items()}
_BATCH_SIZE = 100

# data-only 迁移使用轻量表对象，不把最新模型 metadata 引入历史 migration。
_JSON_TABLES: dict[str, tuple[str, ...]] = {
    "rules": ("definition",),
    "rule_change_logs": ("diff",),
    "rule_set_items": ("params_override",),
    "structure_profiles": ("profile",),
    "review_runs": ("rule_plan", "violations"),
    "rule_executions": ("violations", "extracted", "tool_calls", "llm_io"),
}


def convert_contract_terms(value: Any, mapping: Mapping[str, str] | None = None) -> Any:
    """递归转换精确契约 token；相似前缀字符串必须保持不变。"""
    terms = mapping if mapping is not None else _FORWARD_TERMS
    if isinstance(value, dict):
        return {
            terms.get(str(key), key): convert_contract_terms(child, terms)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [convert_contract_terms(child, terms) for child in value]
    if isinstance(value, str):
        return terms.get(value, value)
    return value


def _json_value(value: Any) -> Any:
    """兼容 SQLite 返回的 JSON 字符串；非法历史字符串原样保留。"""
    if not isinstance(value, str) or not value.strip():
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _light_table(name: str, fields: tuple[str, ...]):
    return table(
        name,
        column("id", sa.BigInteger),
        *(column(field, sa.JSON) for field in fields),
    )


def _migrate_json_columns(conn, terms: Mapping[str, str]) -> None:
    """按主键分批读取并转换 JSON 契约字段，避免一次性载入历史 trace。"""
    for table_name, fields in _JSON_TABLES.items():
        target = _light_table(table_name, fields)
        primary_key = target.c.id
        columns = [primary_key, *(target.c[field] for field in fields)]
        last_id = 0
        while True:
            rows = conn.execute(
                select(*columns)
                .where(primary_key > last_id)
                .order_by(primary_key)
                .limit(_BATCH_SIZE)
            ).mappings()
            batch = list(rows)
            if not batch:
                break
            for row in batch:
                changes: dict[str, Any] = {}
                for field in fields:
                    original = _json_value(row[field])
                    converted = convert_contract_terms(original, terms)
                    if converted != original:
                        changes[field] = converted
                if changes:
                    conn.execute(update(target).where(primary_key == row["id"]).values(**changes))
            last_id = int(batch[-1]["id"])


def _migrate_data_kind(conn, source: str, target: str) -> None:
    concepts = table("concepts", column("data_kind", sa.String))
    conn.execute(update(concepts).where(concepts.c.data_kind == source).values(data_kind=target))


def upgrade() -> None:
    conn = op.get_bind()
    _migrate_data_kind(conn, "hazard_list", "item_list")
    _migrate_json_columns(conn, _FORWARD_TERMS)


def downgrade() -> None:
    conn = op.get_bind()
    _migrate_data_kind(conn, "item_list", "hazard_list")
    _migrate_json_columns(conn, _REVERSE_TERMS)
