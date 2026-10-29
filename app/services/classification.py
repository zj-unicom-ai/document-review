# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Classification CRUD: tenant-owned business data with editable two-level tree."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select, update

from app.core.exceptions import ConflictError, NotFoundError
from app.models.classification import Classification
from app.models.rule import Rule
from app.schemas.classification import ClassificationDeletePreview
from app.services.base import TenantScopedService


class ClassificationService(TenantScopedService[Classification]):
    model = Classification

    def _read_filter(self):
        # 分类是租户业务数据，不再合并平台默认行。
        clauses = [Classification.is_deleted.is_(False)]
        if self.tenant_id:
            clauses.append(Classification.tenant_id == self.tenant_id)
        else:
            clauses.append(Classification.tenant_id == "")
        return clauses

    async def _active_children(self, parent_id: int) -> Sequence[Classification]:
        result = await self.session.execute(
            select(Classification)
            .where(
                Classification.parent_id == parent_id,
                Classification.is_deleted.is_(False),
            )
            .order_by(Classification.sort_order, Classification.classify_id)
        )
        return result.scalars().all()

    async def _validate_classify_id(self, classify_id: int, exclude_id: int | None = None) -> None:
        stmt = select(Classification.id).where(
            Classification.tenant_id == self.tenant_id,
            Classification.classify_id == classify_id,
            Classification.is_deleted.is_(False),
        )
        if exclude_id is not None:
            stmt = stmt.where(Classification.id != exclude_id)
        if await self.session.scalar(stmt.limit(1)) is not None:
            raise ConflictError("分类编号在同一租户内必须唯一")

    async def _resolve_parent(self, parent_id: int | None) -> Classification | None:
        """校验并返回父分类；根分类返回 None。"""
        if parent_id is None:
            return None
        if parent_id == 0:
            raise ConflictError("父级分类不存在")
        try:
            parent = await self.get(parent_id)
        except NotFoundError as exc:
            raise ConflictError("父级分类不存在") from exc
        if parent.parent_id is not None:
            raise ConflictError("父级分类必须是根分类")
        return parent

    async def create(self, data: dict, *, created_by: str = "system") -> Classification:
        await self._validate_classify_id(data["classify_id"])
        parent = await self._resolve_parent(data.get("parent_id"))
        if parent is not None:
            data["level"] = 2
        else:
            data["level"] = 1
        return await super().create(data, created_by=created_by)

    async def update(self, id: int, data: dict, *, updated_by: str = "system") -> Classification:
        obj = await self.get(id)
        next_classify_id = data.get("classify_id", obj.classify_id)
        await self._validate_classify_id(next_classify_id, exclude_id=obj.id)

        parent: Classification | None = None
        # Pydantic exclude_unset 会保留显式 parent_id=null，用于表达改为根分类。
        if "parent_id" in data:
            parent = await self._resolve_parent(data["parent_id"])
            if parent is not None:
                if parent.id == obj.id:
                    raise ConflictError("父级分类不能是当前分类")
                if obj.parent_id is None and await self._active_children(obj.id):
                    raise ConflictError("分类仍存在子分类，不能改为子分类")
                data["level"] = 2
            else:
                data["level"] = 1
            data.pop("parent_id")

        # parent_id 已从 data 移除；外键在基础 update 后补写，保证与派生 level 同步。
        parent_id = parent.id if parent is not None else None
        if "parent_id" not in data:
            data["parent_id"] = parent_id
        updated = await super().update(id, data, updated_by=updated_by)
        await self.session.commit()
        await self.session.refresh(updated)
        return updated

    async def _collect_tree(self, root_id: int) -> list[Classification]:
        root = await self.get(root_id)
        rows = [root]
        frontier = [root.id]
        # 当前业务约束是两级；按后代遍历可实现未来层级扩展时的级联语义。
        while frontier:
            result = await self.session.execute(
                select(Classification).where(
                    Classification.parent_id.in_(frontier),
                    Classification.is_deleted.is_(False),
                )
            )
            children = list(result.scalars().all())
            rows.extend(children)
            frontier = [child.id for child in children]
        return rows

    async def delete_preview(self, id: int) -> ClassificationDeletePreview:
        tree = await self._collect_tree(id)
        classification_ids = [row.id for row in tree]
        rule_count = await self.session.scalar(
            select(func.count())
            .select_from(Rule)
            .where(
                Rule.tenant_id == self.tenant_id,
                Rule.classify_id.in_(classification_ids),
                Rule.is_deleted.is_(False),
            )
        )
        return ClassificationDeletePreview(
            classification_count=len(tree),
            child_count=len(tree) - 1,
            rule_count=int(rule_count or 0),
        )

    async def delete(self, id: int) -> None:  # type: ignore[override]
        tree = await self._collect_tree(id)
        classification_ids = [row.id for row in tree]
        await self.session.execute(
            update(Rule)
            .where(
                Rule.tenant_id == self.tenant_id,
                Rule.classify_id.in_(classification_ids),
                Rule.is_deleted.is_(False),
            )
            .values(classify_id=None)
        )
        for row in tree:
            row.is_deleted = True
        await self.session.commit()
