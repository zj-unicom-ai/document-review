# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Document template CRUD and trial APIs."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import PageDeps
from app.core.config import settings
from app.core.deps import AuthorizedTenant, DBSession, require_menu
from app.core.exceptions import ValidationError
from app.schemas.common import PageResult
from app.schemas.document_template import (
    DocumentTemplateCreate,
    DocumentTemplateFromProfileCreate,
    DocumentTemplateOut,
    DocumentTemplateUpdate,
    TemplateTrialResponse,
)
from app.services.template import DocumentTemplateService

router = APIRouter(dependencies=[Depends(require_menu("system_templates"))])


@router.post("/trial", response_model=TemplateTrialResponse)
async def trial_template(
    session: DBSession,
    tenant_id: AuthorizedTenant,
    file: Annotated[UploadFile, File()],
    rule_set_id: Annotated[int | None, Form()] = None,
):
    """上传样例生成画像并预览规则命中，不创建正式审查 run。"""
    max_bytes = settings.agent_max_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if not content:
        raise ValidationError("上传文件不能为空")
    if len(content) > max_bytes:
        raise ValidationError("上传文件超过大小限制")
    service = DocumentTemplateService(session, tenant_id)
    return await service.trial(content, rule_set_id=rule_set_id)


@router.post(
    "/from-profile/{profile_id}",
    response_model=DocumentTemplateOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_template_from_profile(
    profile_id: int,
    payload: DocumentTemplateFromProfileCreate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
):
    """把已确认画像固化为 active 模板。"""
    service = DocumentTemplateService(session, tenant_id)
    obj = await service.create_from_profile(profile_id, payload)
    return DocumentTemplateOut.model_validate(obj)


@router.get("", response_model=PageResult[DocumentTemplateOut])
async def list_templates(session: DBSession, tenant_id: AuthorizedTenant, page_deps: PageDeps):
    svc = DocumentTemplateService(session, tenant_id)
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[DocumentTemplateOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=DocumentTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: DocumentTemplateCreate, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = DocumentTemplateService(session, tenant_id)
    obj = await svc.create(payload.model_dump())
    return DocumentTemplateOut.model_validate(obj)


@router.get("/{template_id}", response_model=DocumentTemplateOut)
async def get_template(template_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = DocumentTemplateService(session, tenant_id)
    return DocumentTemplateOut.model_validate(await svc.get(template_id))


@router.patch("/{template_id}", response_model=DocumentTemplateOut)
async def update_template(
    template_id: int,
    payload: DocumentTemplateUpdate,
    session: DBSession,
    tenant_id: AuthorizedTenant,
):
    svc = DocumentTemplateService(session, tenant_id)
    return DocumentTemplateOut.model_validate(
        await svc.update(template_id, payload.model_dump(exclude_unset=True))
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = DocumentTemplateService(session, tenant_id)
    await svc.delete(template_id)
    return None
