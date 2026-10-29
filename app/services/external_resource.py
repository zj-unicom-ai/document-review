# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""ExternalResource CRUD service."""

from app.models.external_resource import ExternalResource
from app.services.base import TenantScopedService


class ExternalResourceService(TenantScopedService[ExternalResource]):
    model = ExternalResource
