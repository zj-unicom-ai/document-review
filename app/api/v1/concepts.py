# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Concept CRUD (tenant-scoped; platform concepts read-only)."""

from fastapi import APIRouter, Depends, status

from app.api.deps import PageDeps
from app.core.deps import AuthorizedTenant, DBSession, require_menu
from app.schemas.common import PageResult
from app.schemas.concept import ConceptCreate, ConceptOut, ConceptUpdate
from app.services.concept import ConceptService

router = APIRouter(dependencies=[Depends(require_menu("concepts"))])


@router.get("", response_model=PageResult[ConceptOut])
async def list_concepts(session: DBSession, tenant_id: AuthorizedTenant, page_deps: PageDeps):
    svc = ConceptService(session, tenant_id)
    rows, total = await svc.list(page=page_deps.page, page_size=page_deps.page_size, q=page_deps.q)
    return PageResult(
        items=[ConceptOut.model_validate(r) for r in rows],
        total=total,
        page=page_deps.page,
        page_size=page_deps.page_size,
    )


@router.post("", response_model=ConceptOut, status_code=status.HTTP_201_CREATED)
async def create_concept(payload: ConceptCreate, session: DBSession, tenant_id: AuthorizedTenant):
    svc = ConceptService(session, tenant_id)
    obj = await svc.create(payload.model_dump())
    return ConceptOut.model_validate(obj)


@router.get("/{concept_id}", response_model=ConceptOut)
async def get_concept(concept_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = ConceptService(session, tenant_id)
    return ConceptOut.model_validate(await svc.get(concept_id))


@router.patch("/{concept_id}", response_model=ConceptOut)
async def update_concept(
    concept_id: int, payload: ConceptUpdate, session: DBSession, tenant_id: AuthorizedTenant
):
    svc = ConceptService(session, tenant_id)
    return ConceptOut.model_validate(
        await svc.update(concept_id, payload.model_dump(exclude_unset=True))
    )


@router.delete("/{concept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_concept(concept_id: int, session: DBSession, tenant_id: AuthorizedTenant):
    svc = ConceptService(session, tenant_id)
    await svc.delete(concept_id)
    return None
