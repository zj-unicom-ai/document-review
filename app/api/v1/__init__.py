# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""v1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    classifications,
    concepts,
    evaluations,
    external_resources,
    menu_permissions,
    operators,
    reviews,
    roles,
    rule_sets,
    rules,
    templates,
    tenants,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])
api_v1_router.include_router(tenants.router, prefix="/tenants", tags=["tenants"])
api_v1_router.include_router(users.router, prefix="/users", tags=["users"])
api_v1_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_v1_router.include_router(
    menu_permissions.router, prefix="/menu-permissions", tags=["menu-permissions"]
)
api_v1_router.include_router(operators.router, prefix="/operators", tags=["operators"])
api_v1_router.include_router(concepts.router, prefix="/concepts", tags=["concepts"])
api_v1_router.include_router(
    classifications.router, prefix="/classifications", tags=["classifications"]
)
api_v1_router.include_router(rules.router, prefix="/rules", tags=["rules"])
api_v1_router.include_router(rule_sets.router, prefix="/rule-sets", tags=["rule-sets"])
api_v1_router.include_router(templates.router, prefix="/templates", tags=["templates"])
api_v1_router.include_router(
    external_resources.router, prefix="/external-resources", tags=["external-resources"]
)
api_v1_router.include_router(reviews.router, prefix="/reviews", tags=["reviews"])
