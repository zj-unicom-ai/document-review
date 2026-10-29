# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Idempotent seed loader. Run with: python -m app.seed.load_seed

BL-062：平台不再预置业务概念。默认仅同步算子机制元数据；可选分类 /
规则 / 规则集数据不随公开发行包提供，仅 SEED_STANDARD_RULES=true 时写入。
概念完全由租户按需自建（界面或 API）。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sqlalchemy import delete, select

from app.core.config import settings
from app.core.db import dispose_engine, get_sessionmaker
from app.core.logging import configure_logging, get_logger
from app.models.classification import Classification
from app.models.concept import Concept
from app.models.operator import Operator
from app.models.rule import Rule
from app.models.rule_set import RuleSet, RuleSetItem
from app.operators import all_operators
from app.operators.registry import known_op_codes

log = get_logger("seed")
DATA_DIR = Path(__file__).parent / "data"


def _load_json(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


async def seed_classifications(session) -> tuple[int, int]:
    """Insert first-level rows, then second-level with parent FK."""
    data = _load_json("classifications.json")
    # map classify_id (natural) -> id (surrogate)
    parent_id_map: dict[int, int] = {}
    inserted, updated = 0, 0
    for row in data["first_level"]:
        existing = (
            await session.execute(
                select(Classification).where(
                    Classification.tenant_id == "",
                    Classification.classify_id == row["classify_id"],
                    Classification.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            obj = Classification(
                tenant_id="",
                classify_id=row["classify_id"],
                level=row["level"],
                name=row["name"],
                description=row.get("description"),
                sort_order=row.get("sort_order", 0),
            )
            session.add(obj)
            await session.flush()  # need id
            parent_id_map[row["classify_id"]] = obj.id
            inserted += 1
        else:
            existing.name = row["name"]
            existing.description = row.get("description")
            existing.sort_order = row.get("sort_order", 0)
            parent_id_map[row["classify_id"]] = existing.id
            updated += 1
    await session.commit()
    # second-level
    for row in data["second_level"]:
        parent_sid = parent_id_map.get(row["parent"])
        if parent_sid is None:
            log.warning("parent missing", parent=row["parent"], child=row["classify_id"])
            continue
        existing = (
            await session.execute(
                select(Classification).where(
                    Classification.tenant_id == "",
                    Classification.classify_id == row["classify_id"],
                    Classification.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                Classification(
                    tenant_id="",
                    classify_id=row["classify_id"],
                    parent_id=parent_sid,
                    level=row["level"],
                    name=row["name"],
                    sort_order=row["classify_id"],
                )
            )
            inserted += 1
        else:
            existing.name = row["name"]
            existing.parent_id = parent_sid
            updated += 1
    await session.commit()
    return inserted, updated


async def sync_operators(session) -> tuple[int, int]:
    """Sync in-memory operator registry to the operator table."""
    inserted, updated = 0, 0
    removed = 0
    for op_code, cls in all_operators():
        existing = (
            await session.execute(select(Operator).where(Operator.op_code == op_code))
        ).scalar_one_or_none()
        params_schema = cls.params_model.model_json_schema()
        # drop title from schema for compactness
        params_schema.pop("title", None)
        executor = f"{cls.__module__}:{cls.__name__}"
        if existing is None:
            session.add(
                Operator(
                    op_code=op_code,
                    name=cls.name,
                    description=cls.description,
                    applicable_data_kind=cls.applicable_data_kind,
                    params_schema=params_schema,
                    result_semantics=cls.result_semantics,
                    executor=executor,
                    model_profile=cls.model_profile,
                )
            )
            inserted += 1
        else:
            existing.name = cls.name
            existing.description = cls.description
            existing.applicable_data_kind = cls.applicable_data_kind
            existing.params_schema = params_schema
            existing.result_semantics = cls.result_semantics
            existing.executor = executor
            existing.model_profile = cls.model_profile
            updated += 1
    # BL-062 算子收敛后，operator 表是代码 registry 的登记视图；
    # 不在 registry 中的旧 op_code 直接清除，不留兼容别名。
    valid_codes = set(known_op_codes())
    stale = (await session.execute(select(Operator))).scalars().all()
    for row in stale:
        if row.op_code not in valid_codes:
            await session.delete(row)
            removed += 1
            log.info("remove stale operator", op_code=row.op_code)
    await session.commit()
    if removed:
        log.info("operator sync removed stale rows", removed=removed)
    return inserted, updated


def _validate_ops(rule_code: str, ops: list[dict], op_codes: set[str]) -> None:
    """递归校验规则算子，避免坏种子进入库后才在引擎暴露。"""
    for item in ops:
        op_code = item.get("op")
        if op_code not in op_codes:
            raise ValueError(f"rule={rule_code} unknown operator: {op_code}")
        fail = item.get("fail") or {}
        if not fail.get("title") or not fail.get("content"):
            raise ValueError(f"rule={rule_code} op={op_code} fail template is incomplete")
        child_ops = item.get("params", {}).get("child_ops", [])
        _validate_ops(rule_code, child_ops, op_codes)


def _referenced_concepts(definition: dict) -> list[str]:
    """收集 DSL 中所有概念引用，主锚点与辅助锚点同等校验。"""
    refs = [definition["anchor"]["concept"]]
    refs.extend(definition.get("secondary_concepts", []))
    refs.extend(definition.get("context_concepts", []))
    iterate = definition.get("iterate")
    if iterate:
        refs.append(iterate["concept"])
    return refs


async def seed_rules(session) -> tuple[int, int]:
    """Upsert platform standard rules by (tenant_id, rule_code)."""
    data = _load_json("rules.json")
    concept_rows = (
        (
            await session.execute(
                select(Concept).where(Concept.tenant_id == "", Concept.is_deleted.is_(False))
            )
        )
        .scalars()
        .all()
    )
    concepts = {row.concept_code for row in concept_rows}
    classification_rows = (
        (
            await session.execute(
                select(Classification).where(
                    Classification.tenant_id == "",
                    Classification.is_deleted.is_(False),
                    Classification.level == 2,
                )
            )
        )
        .scalars()
        .all()
    )
    classifications = {row.classify_id: row.id for row in classification_rows}
    op_codes = set(known_op_codes())

    # 先校验整批再写入，保证任意引用错误都不会留下半批种子。
    seen: set[str] = set()
    for row in data:
        rule_code = row["rule_code"]
        if rule_code in seen:
            raise ValueError(f"duplicate rule_code in seed: {rule_code}")
        seen.add(rule_code)
        for concept in _referenced_concepts(row["definition"]):
            if concept not in concepts:
                raise ValueError(f"rule={rule_code} unknown concept: {concept}")
        classify_natural_id = row.get("classify_natural_id")
        if classify_natural_id is not None and classify_natural_id not in classifications:
            raise ValueError(f"rule={rule_code} unknown classification: {classify_natural_id}")
        _validate_ops(rule_code, row["definition"].get("ops", []), op_codes)

    existing_rows = (
        (await session.execute(select(Rule).where(Rule.tenant_id == ""))).scalars().all()
    )
    existing = {row.rule_code: row for row in existing_rows if not row.is_deleted}
    inserted, updated = 0, 0
    for row in data:
        rule_code = row["rule_code"]
        classify_natural_id = row.get("classify_natural_id")
        values = {
            "name": row["name"],
            "description": row.get("description"),
            "rule_type": row["rule_type"],
            "classify_id": (
                classifications[classify_natural_id] if classify_natural_id is not None else None
            ),
            "severity_default": row.get("severity_default", "一般"),
            "blocking_policy": row.get("blocking_policy", "block"),
            "on_error_policy": row.get("on_error_policy", "annotate"),
            "output_mode": row.get("output_mode", "violations"),
            "model_profile": row.get("model_profile"),
            "enabled": row.get("enabled", True),
            "definition": row["definition"],
            "note": row.get("note"),
        }
        current = existing.get(rule_code)
        if current is None:
            session.add(Rule(tenant_id="", rule_code=rule_code, **values))
            inserted += 1
        else:
            for key, value in values.items():
                setattr(current, key, value)
            updated += 1
    await session.commit()
    return inserted, updated


async def seed_rule_sets(session) -> tuple[int, int]:
    """Upsert platform standard packs and rebuild their seed items."""
    data = _load_json("rule_sets.json")
    rule_rows = (
        (
            await session.execute(
                select(Rule).where(Rule.tenant_id == "", Rule.is_deleted.is_(False))
            )
        )
        .scalars()
        .all()
    )
    rules = {row.rule_code: row for row in rule_rows}

    # 先校验所有 item 引用，再删除重建，失败时不改变现有规则集。
    for pack in data:
        for item in pack["items"]:
            rule_code = item["rule_code"]
            if rule_code not in rules:
                raise ValueError(f"rule_set={pack['name']} unknown rule: {rule_code}")

    existing_rows = (
        (
            await session.execute(
                select(RuleSet).where(RuleSet.tenant_id == "", RuleSet.is_standard_pack.is_(True))
            )
        )
        .scalars()
        .all()
    )
    existing = {row.name: row for row in existing_rows}
    inserted, updated = 0, 0
    for pack in data:
        current = existing.get(pack["name"])
        if current is None:
            current = RuleSet(
                tenant_id="",
                name=pack["name"],
                template_id=None,
                is_standard_pack=True,
                description=pack.get("description"),
            )
            session.add(current)
            await session.flush()
            inserted += 1
        else:
            current.description = pack.get("description")
            updated += 1

        await session.execute(delete(RuleSetItem).where(RuleSetItem.rule_set_id == current.id))
        for item in pack["items"]:
            session.add(
                RuleSetItem(
                    rule_set_id=current.id,
                    rule_id=rules[item["rule_code"]].id,
                    execution_order=item.get("execution_order", 0),
                    enabled=item.get("enabled", True),
                    params_override=item.get("params_override", {}),
                )
            )
    await session.commit()
    return inserted, updated


async def main() -> None:
    configure_logging(settings.app_log_level)
    log.info("seed.start", env=settings.app_env, db=settings.async_database_url.split("@")[-1])

    sm = get_sessionmaker()
    try:
        async with sm() as session:
            oi, ou = await sync_operators(session)
            log.info("seed.operators", inserted=oi, updated=ou)

            if settings.seed_standard_rules:
                # 可选分类数据只在显式启用规则包加载时写入。
                ci, cu = await seed_classifications(session)
                log.info("seed.classifications", inserted=ci, updated=cu)

                ri, ru = await seed_rules(session)
                log.info("seed.rules", inserted=ri, updated=ru)

                psi, psu = await seed_rule_sets(session)
                log.info("seed.rule_sets", inserted=psi, updated=psu)
            else:
                log.info("seed.rules_skipped", reason="standard_rules_disabled")
    finally:
        # 一次性 seed 命令同样需要释放全局 engine，保证退出时无悬挂数据库连接。
        await dispose_engine()

    log.info("seed.done")


if __name__ == "__main__":
    asyncio.run(main())
