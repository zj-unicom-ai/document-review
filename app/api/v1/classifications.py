# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Classification CRUD (tenant-scoped)."""

from fastapi import APIRouter, Depends, status

from app.api.deps import PageDeps
from app.core.deps import AuthorizedTenant, DBSession, require_menu
from app.schemas.classification import (
    ClassificationCreate,
    ClassificationDeletePreview,
    ClassificationOut,
    ClassificationUpdate,
)
from app.schemas.common import PageResult
from app.services.classification import ClassificationService

router = APIRouter(dependencies=[Depends(require_menu("classifications"))])


@router.get("", response_model=PageResult[ClassificationOut])
async def list_classifications(
    session: DBSession, tenant_id: AuthorizedTenant, page_deps: PageDeps
):
    svc = ClassificationService(session, tenant_id)
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[ClassificationOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=ClassificationOut, status_code=status.HTTP_201_CREATED)
async def create_classification(
    payload: ClassificationCreate, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = ClassificationService(session, tenant_id)
    obj = await svc.create(payload.model_dump())
    return ClassificationOut.model_validate(obj)


@router.get("/{cls_id}", response_model=ClassificationOut)
async def get_classification(cls_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = ClassificationService(session, tenant_id)
    return ClassificationOut.model_validate(await svc.get(cls_id))


@router.patch("/{cls_id}", response_model=ClassificationOut)
async def update_classification(
    cls_id: int, payload: ClassificationUpdate, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = ClassificationService(session, tenant_id)
    return ClassificationOut.model_validate(
        await svc.update(cls_id, payload.model_dump(exclude_unset=True))
    )


@router.get("/{cls_id}/delete-preview", response_model=ClassificationDeletePreview)
async def preview_classification_deletion(
    cls_id: int, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = ClassificationService(session, tenant_id)
    return await svc.delete_preview(cls_id)


@router.delete("/{cls_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_classification(cls_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = ClassificationService(session, tenant_id)
    await svc.delete(cls_id)
    return None
