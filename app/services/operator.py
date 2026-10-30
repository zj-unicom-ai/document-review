# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Operator registry is read-only after seed; no mutations from API."""

from app.models.operator import Operator
from app.services.base import TenantScopedService


class OperatorService(TenantScopedService[Operator]):
    model = Operator
    is_platform_table = True  # operators are platform-level (no tenant_id)
