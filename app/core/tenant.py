# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""租户身份的统一归一化与格式边界。"""

from __future__ import annotations

import re

from app.core.exceptions import ValidationError

_TENANT_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def normalize_tenant_id(value: str | None) -> str:
    """归一化请求租户 ID；空值表示平台级。"""
    if value is None:
        return ""
    tenant = value.strip()
    if not tenant:
        return ""
    if len(tenant) > 64 or not _TENANT_ID.fullmatch(tenant):
        raise ValidationError("X-Tenant-Id 只能包含字母、数字、下划线或短横线，且不超过 64 字符")
    return tenant
