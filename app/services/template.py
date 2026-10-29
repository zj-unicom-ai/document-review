# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""DocumentTemplate CRUD 与模板试跑 / 画像固化服务。"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import re
import shutil
import uuid

try:
    import fcntl
except ImportError:  # pragma: no cover 非 POSIX 部署依赖数据库行锁兜底
    fcntl = None
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select, update

from app.core.config import settings
from app.core.exceptions import ConflictError, ImmutableError, NotFoundError, ValidationError
from app.core.storage import tenant_storage_path
from app.engine.document import DocumentContext
from app.engine.evidence import resolve_profile_evidence
from app.engine.executor import run_rule
from app.engine.planner import build_rule_plan
from app.engine.profile import build_profile, concept_set_hash
from app.engine.profile_discovery import ProfileDiscovery
from app.integrations.llm import build_llm_service
from app.integrations.mineru import MineruArtifactParser
from app.models.concept import Concept
from app.models.document_template import DocumentTemplate
from app.models.rule_set import RuleSet
from app.models.structure_profile import StructureProfile as StructureProfileRow
from app.schemas.document_template import (
    DocumentTemplateFromProfileCreate,
    TemplateTrialResponse,
    TemplateTrialRulePreview,
)
from app.schemas.profile import StructureProfile
from app.services.base import TenantScopedService
from app.utils.pdf_content_parse_utils import PDFParse


class DocumentTemplateService(TenantScopedService[DocumentTemplate]):
    model = DocumentTemplate

    async def trial(
        self,
        source_bytes: bytes,
        *,
        rule_set_id: int | None = None,
        mineru_parser: PDFParse | None = None,
    ) -> TemplateTrialResponse:
        """试跑样例并持久化可固化画像；不创建正式审查记录。"""
        if rule_set_id is not None:
            await self._get_visible_rule_set(rule_set_id)
        digest = hashlib.sha256(source_bytes).hexdigest()
        shared_artifact = tenant_storage_path(self.tenant_id, "artifacts", digest, "extracted")
        trial_root = tenant_storage_path(self.tenant_id, "trials", uuid.uuid4().hex)
        created_temp_source = False
        try:
            try:
                if not _is_complete_artifact(shared_artifact):
                    source_path = trial_root / "source.pdf"
                    await asyncio.to_thread(source_path.parent.mkdir, parents=True, exist_ok=True)
                    created_temp_source = True
                    await asyncio.to_thread(source_path.write_bytes, source_bytes)
                    await PDFParse.locate_or_build_artifact_async(
                        source_path,
                        output_dir=shared_artifact,
                        parser=mineru_parser,
                    )
                parsed = await MineruArtifactParser(shared_artifact).parse(
                    shared_artifact / "upload_origin.pdf"
                )
            except Exception as exc:
                raise ValidationError(f"样例 PDF 解析失败: {exc}") from exc

            doc = DocumentContext(parsed)
            vocabulary = await self._concept_vocabulary()
            concept_hash = concept_set_hash(vocabulary)
            discovery_service = (
                build_llm_service(settings) if settings.llm_profile_discovery else None
            )
            discover = None
            if discovery_service is not None:

                async def discover(doc: DocumentContext):
                    return await self._discover_with_service(discovery_service, doc)

            profile_row = await build_profile(
                self.session,
                self.tenant_id,
                digest,
                doc,
                source_run_id=None,
                discover=discover,
                concept_hash=concept_hash,
            )
            if profile_row.source_run_id is not None:
                profile_row = _clone_profile_for_trial(profile_row)
                self.session.add(profile_row)
                await self.session.flush()
            suggested = _suggested_detect_conditions(doc)
            profile_dict = resolve_profile_evidence(
                doc,
                vocabulary,
                dict(profile_row.profile or {}),
            )
            raw = dict(profile_dict.get("raw") or {})
            raw["template_trial"] = {
                "suggested_detect_conditions": suggested,
                "rule_set_id": rule_set_id,
            }
            profile_dict["raw"] = raw
            profile_row.profile = profile_dict
            await self.session.commit()
            await self.session.refresh(profile_row)

            rule_set, selection_reason = await self._select_rule_set(rule_set_id, profile_dict)
            preview: list[TemplateTrialRulePreview] = []
            if rule_set is not None:
                plan = await build_rule_plan(self.session, self.tenant_id, rule_set, profile_dict)
                execution_doc = DocumentContext(parsed, profile_dict)
                llm_service = build_llm_service(settings)
                for item in plan:
                    result = await run_rule(item, execution_doc, llm_service=llm_service)
                    preview.append(
                        TemplateTrialRulePreview(
                            rule_id=item.rule_id,
                            rule_code=item.rule_code,
                            rule_name=item.rule_name,
                            rule_type=item.rule_type,
                            status=result.status,
                            violations=result.violations,
                            extracted=result.extracted,
                            skip_reason=result.skip_reason,
                            error=result.error,
                            duration_ms=result.duration_ms,
                        )
                    )

            return TemplateTrialResponse(
                profile_id=profile_row.id,
                file_sha256=digest,
                discovery_method=profile_row.discovery_method,
                template_id=profile_row.template_id,
                doc_summary=profile_dict.get("doc_summary"),
                bindings=list(profile_dict.get("bindings") or []),
                suggested_detect_conditions=suggested,
                rule_set_id=rule_set.id if rule_set else None,
                rule_set_selection_reason=selection_reason,
                rule_preview=preview,
            )
        finally:
            if created_temp_source:
                await asyncio.to_thread(shutil.rmtree, trial_root, ignore_errors=True)
                with contextlib.suppress(OSError):
                    await asyncio.to_thread(trial_root.parent.rmdir)

    async def create_from_profile(
        self,
        profile_id: int,
        payload: DocumentTemplateFromProfileCreate,
    ) -> DocumentTemplate:
        """把当前租户已确认画像固化为 active 模板。"""
        async with self._profile_fix_lock(profile_id):
            profile = await self._get_own_profile(profile_id)
            contract = _validated_profile_contract(profile)
            conditions = _validated_detect_conditions(payload.detect_conditions)

            duplicated = (
                await self.session.execute(
                    select(DocumentTemplate)
                    .where(
                        DocumentTemplate.source_profile_id == profile_id,
                        DocumentTemplate.tenant_id == self.tenant_id,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if duplicated is not None:
                raise ConflictError("该画像已固化为模板，不能重复固化")

            return await self.create(
                {
                    "name": payload.name,
                    "status": "active",
                    "description": payload.description,
                    "detect_conditions": conditions,
                    "concept_bindings": [
                        binding.model_dump(mode="json") for binding in contract.bindings
                    ],
                    "source_profile_id": profile_id,
                }
            )

    async def delete(self, id: int) -> None:  # type: ignore[override]
        """删除模板；画像缓存只解除引用，规则集引用必须先由用户处理。"""
        template = await self.get(id)
        if self.tenant_id and template.tenant_id == "":
            raise ImmutableError("cannot delete platform-level templates")

        referenced_by_rule_set = (
            await self.session.execute(select(RuleSet.id).where(RuleSet.template_id == id))
        ).first()
        if referenced_by_rule_set is not None:
            raise ConflictError("模板仍被规则集引用，请先调整规则集绑定后再删除")

        # 画像缓存是历史产物；模板删除后保留缓存行并解除可空引用。
        await self.session.execute(
            update(StructureProfileRow)
            .where(StructureProfileRow.template_id == id)
            .values(template_id=None)
        )
        await self.session.delete(template)
        if hasattr(template, "updated_by"):
            template.updated_by = "system"
        await self.session.commit()

    @contextlib.asynccontextmanager
    async def _profile_fix_lock(self, profile_id: int):
        """画像固化使用文件锁串行化，数据库行锁作为多进程兜底。"""
        lock_path = tenant_storage_path(self.tenant_id, "locks", f"template-{profile_id}.lock")

        def acquire() -> int | None:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            if fcntl is None:
                return None
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
            except Exception:
                os.close(descriptor)
                raise
            return descriptor

        descriptor = await asyncio.to_thread(acquire)
        try:
            yield
        finally:
            if descriptor is not None:
                await asyncio.to_thread(fcntl.flock, descriptor, fcntl.LOCK_UN)
                await asyncio.to_thread(os.close, descriptor)

    async def _discover_with_service(self, service, doc: DocumentContext):
        return await ProfileDiscovery(service).discover(doc, await self._concept_vocabulary())

    async def _concept_vocabulary(self) -> list[dict[str, Any]]:
        rows = await self._concept_rows()
        return [
            {
                "concept_code": row.concept_code,
                "concept_name": row.concept_name,
                "aliases": row.aliases or [],
                "data_kind": row.data_kind,
            }
            for row in rows
        ]

    async def _concept_rows(self) -> list[Concept]:
        return list(
            (
                await self.session.execute(
                    select(Concept).where(
                        Concept.is_deleted.is_(False),
                        Concept.tenant_id.in_(["", self.tenant_id]),
                    )
                )
            )
            .scalars()
            .all()
        )

    async def _select_rule_set(
        self, rule_set_id: int | None, profile: dict[str, Any]
    ) -> tuple[RuleSet | None, str]:
        if rule_set_id is not None:
            rule_set = await self._get_visible_rule_set(rule_set_id)
            return rule_set, "已按显式 rule_set_id 选择"

        template_id = profile.get("template_id")
        if template_id is None:
            return None, "未命中模板且未显式选择规则集，未执行规则预览"
        rows = (
            (
                await self.session.execute(
                    select(RuleSet).where(
                        RuleSet.template_id == template_id,
                        or_(RuleSet.tenant_id == "", RuleSet.tenant_id == self.tenant_id),
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(rows) == 1:
            return rows[0], "已按画像命中模板的唯一规则集选择"
        if not rows:
            return None, "画像命中模板未绑定规则集，未执行规则预览"
        return None, f"模板绑定 {len(rows)} 个规则集，未唯一确定，未执行规则预览"

    async def _get_visible_rule_set(self, rule_set_id: int) -> RuleSet:
        rule_set = (
            await self.session.execute(
                select(RuleSet).where(
                    RuleSet.id == rule_set_id,
                    or_(RuleSet.tenant_id == "", RuleSet.tenant_id == self.tenant_id),
                )
            )
        ).scalar_one_or_none()
        if rule_set is None:
            raise ValidationError(f"规则集不存在或租户不可见: {rule_set_id}")
        return rule_set

    async def _get_own_profile(self, profile_id: int) -> StructureProfileRow:
        stmt = (
            select(StructureProfileRow)
            .where(
                StructureProfileRow.id == profile_id,
                StructureProfileRow.tenant_id == self.tenant_id,
            )
            .with_for_update()
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"structure profile id={profile_id} not found")
        return row


def _is_complete_artifact(path: Path) -> bool:
    if not path.is_dir():
        return False
    entries = list(path.iterdir())
    return (
        (path / "full.md").is_file()
        and (path / "layout.json").is_file()
        and any(item.name.endswith("_content_list.json") for item in entries)
        and any(item.name.endswith("_origin.pdf") for item in entries)
    )


def _clone_profile_for_trial(profile: StructureProfileRow) -> StructureProfileRow:
    """把正式 run 画像克隆为试跑画像，避免污染正式缓存。"""
    profile_data = dict(profile.profile or {})
    raw = dict(profile_data.get("raw") or {})
    raw.pop("template_trial", None)
    profile_data["raw"] = raw
    return StructureProfileRow(
        tenant_id=profile.tenant_id,
        file_sha256=profile.file_sha256,
        profile=profile_data,
        template_set_hash=profile.template_set_hash,
        discovery_method=profile.discovery_method,
        template_id=profile.template_id,
        llm_trace_id=profile.llm_trace_id,
        source_run_id=None,
    )


def _suggested_detect_conditions(doc: DocumentContext) -> list[dict[str, Any]]:
    """从解析结果给出可编辑的保守识别条件。"""
    titles = [
        item["title"]
        for item in doc.get_section_tree(max_sections=20)
        if str(item.get("title", "")).strip()
    ]
    if titles:
        return [
            {"type": "section_title_regex", "pattern": re.escape(title)} for title in titles[:2]
        ]
    summary = doc.get_first_page_summary(max_chars=200).strip()
    keyword = summary.splitlines()[0][:40] if summary else ""
    if not keyword:
        return []
    return [{"type": "md_contains", "keyword": keyword}]


def _validated_profile_contract(profile: StructureProfileRow) -> StructureProfile:
    try:
        contract = StructureProfile.model_validate(profile.profile or {})
    except Exception as exc:
        raise ValidationError("画像结构不合法，不能固化") from exc
    valid = [
        binding for binding in contract.bindings if binding.status == "bound" and binding.targets
    ]
    if not valid:
        raise ValidationError("画像缺少有效绑定，不能固化为 active 模板")
    contract.bindings = valid
    return contract


def _validated_detect_conditions(conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not conditions:
        raise ValidationError("识别条件不能为空")
    for condition in conditions:
        condition_type = condition.get("type")
        if condition_type == "section_title_regex":
            pattern = condition.get("pattern")
            if not isinstance(pattern, str) or not pattern.strip():
                raise ValidationError("section_title_regex.pattern 不能为空")
            try:
                re.compile(pattern)
            except re.error as exc:
                raise ValidationError(f"章节正则不合法: {exc}") from exc
        elif condition_type == "md_contains":
            keyword = condition.get("keyword")
            if not isinstance(keyword, str) or not keyword.strip():
                raise ValidationError("md_contains.keyword 不能为空")
        elif condition_type == "table_field_contains":
            field = condition.get("field")
            if not isinstance(field, str) or not field.strip():
                raise ValidationError("table_field_contains.field 不能为空")
            keywords = condition.get("keywords")
            if not isinstance(keywords, list) or not keywords:
                raise ValidationError("table_field_contains.keywords 不能为空")
            if not all(isinstance(keyword, str) and keyword.strip() for keyword in keywords):
                raise ValidationError("table_field_contains.keywords 含空值")
        else:
            raise ValidationError(f"不支持的模板识别条件类型: {condition_type}")
    return conditions
