# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""structured 规则样例试跑服务；结果只返回给调用方，不落正式审查记录。"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import shutil
import time
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.storage import tenant_storage_path
from app.core.tenant import normalize_tenant_id
from app.engine.document import DocumentContext
from app.engine.executor import run_rule
from app.engine.planner import build_rule_plan_for_draft
from app.engine.profile import concept_set_hash, load_profile_snapshot
from app.integrations.llm import build_llm_service
from app.integrations.mineru import MineruArtifactParser
from app.models.concept import Concept
from app.schemas.rule import RuleCreate, RuleTrialProfileSummary, RuleTrialResponse
from app.services.rule_definition import validate_rule_definition
from app.utils.pdf_content_parse_utils import PDFParse


class RuleTrialService:
    """单条 structured 规则草稿的样例调试边界。"""

    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = normalize_tenant_id(tenant_id)

    async def trial(
        self,
        payload: RuleCreate,
        source_bytes: bytes,
        *,
        mineru_parser: PDFParse | None = None,
    ) -> RuleTrialResponse:
        """校验草稿、解析样例并执行单条规则。"""
        # BL-062 后主流规则为 hybrid（text/vision 判定），试跑同步放开；
        # llm 类型走 Agent 工具子图，仍由正式审查链路承担。
        if payload.rule_type not in ("structured", "hybrid"):
            raise ValidationError("规则样例试跑当前仅支持 structured / hybrid 规则")
        await validate_rule_definition(
            self.session,
            self.tenant_id,
            payload.rule_type,
            payload.definition,
        )

        digest = hashlib.sha256(source_bytes).hexdigest()
        shared_artifact = tenant_storage_path(
            self.tenant_id,
            "artifacts",
            digest,
            "extracted",
        )
        trial_root = tenant_storage_path(self.tenant_id, "trials", uuid.uuid4().hex)
        artifact_dir = shared_artifact
        created_temp_artifact = False
        try:
            try:
                if not _is_complete_artifact(shared_artifact):
                    source_path = trial_root / "source.pdf"
                    artifact_dir = trial_root / "extracted"
                    await asyncio.to_thread(source_path.parent.mkdir, parents=True, exist_ok=True)
                    await asyncio.to_thread(source_path.write_bytes, source_bytes)
                    created_temp_artifact = True
                    await PDFParse.build_artifact_async(
                        source_path,
                        output_dir=artifact_dir,
                        parser=mineru_parser,
                    )

                parsed = await MineruArtifactParser(artifact_dir).parse(
                    artifact_dir / "upload_origin.pdf"
                )
            except Exception as exc:
                raise ValidationError(f"样例 PDF 解析失败: {exc}") from exc
            concept_rows = (
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
            concept_hash = concept_set_hash(
                [
                    {
                        "concept_code": row.concept_code,
                        "concept_name": row.concept_name,
                        "aliases": row.aliases or [],
                        "data_kind": row.data_kind,
                    }
                    for row in concept_rows
                ]
            )
            profile, profile_summary = await load_profile_snapshot(
                self.session,
                self.tenant_id,
                digest,
                DocumentContext(parsed),
                concept_hash=concept_hash,
            )
            plan = await build_rule_plan_for_draft(self.session, self.tenant_id, payload, profile)
            started = time.monotonic()
            result = await run_rule(
                plan,
                DocumentContext(parsed, profile),
                llm_service=build_llm_service(settings),
            )
            # 执行器内部用 success 表示单规则完成；试跑契约与 ReviewRun 的 completed 对齐。
            status = "completed" if result.status == "success" else result.status
            return RuleTrialResponse(
                status=status,
                violations=result.violations,
                extracted=result.extracted,
                skip_reason=result.skip_reason,
                error=result.error,
                duration_ms=int((time.monotonic() - started) * 1000),
                binding_status=plan.binding_status,
                profile_summary=RuleTrialProfileSummary.model_validate(profile_summary),
            )
        finally:
            if created_temp_artifact:
                await asyncio.to_thread(shutil.rmtree, trial_root, ignore_errors=True)
                # 常规失败后保留空的租户目录没有价值，一并移除；非空时忽略避免误删并发试跑。
                with contextlib.suppress(OSError):
                    await asyncio.to_thread(trial_root.parent.rmdir)


def _is_complete_artifact(path: Path) -> bool:
    """只读判断共享 artifact 是否完整，试跑绝不修改共享缓存。"""
    if not path.is_dir():
        return False
    entries = list(path.iterdir())
    return (
        (path / "full.md").is_file()
        and (path / "layout.json").is_file()
        and any(item.name.endswith("_content_list.json") for item in entries)
        and any(item.name.endswith("_origin.pdf") for item in entries)
    )
