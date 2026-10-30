# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""storage 路径统一组装与边界校验。"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.tenant import normalize_tenant_id


def _storage_root() -> Path:
    return Path(settings.storage_root).resolve()


def _validate_segment(segment: str | Path, *, label: str) -> str:
    """确保调用方传入的是单一安全路径段，防止内部拼接被重置。"""
    value = str(segment)
    if (
        not value
        or value in (".", "..")
        or "/" in value
        or "\\" in value
        or Path(value).is_absolute()
    ):
        raise ValidationError(f"{label} 必须是单个安全路径段")
    return value


def storage_path(*segments: str | Path) -> Path:
    """组装 storage 内路径，并保证 resolve 后不离开 storage 根。"""
    root = _storage_root()
    safe_segments = [_validate_segment(segment, label="storage 路径段") for segment in segments]
    candidate = root.joinpath(*safe_segments).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise ValidationError("storage 路径不能越出 storage 根")
    return candidate


def tenant_storage_path(tenant_id: str | None, *segments: str | Path) -> Path:
    """先校验租户段，再按“storage/类别/租户/...”组装路径。"""
    tenant = normalize_tenant_id(tenant_id)
    if not segments:
        raise ValidationError("租户 storage 路径必须包含类别段")
    category = _validate_segment(segments[0], label="storage 类别")
    rest = [_validate_segment(segment, label="storage 路径段") for segment in segments[1:]]
    root = _storage_root()
    tenant_parts = [category, tenant] if tenant else [category]
    base = root.joinpath(*tenant_parts)
    candidate = base.joinpath(*rest).resolve()
    if candidate != base and not candidate.is_relative_to(base):
        raise ValidationError("storage 路径不能越出当前租户 storage 子树")
    if candidate != root and not candidate.is_relative_to(root):
        raise ValidationError("storage 路径不能越出 storage 根")
    return candidate


def resolve_tenant_storage_path(
    path: str | Path,
    tenant_id: str | None,
    category: str | Path,
) -> Path:
    """解析既有路径，并要求 canonical 结果仍在当前租户类别子树内。"""
    tenant = normalize_tenant_id(tenant_id)
    safe_category = _validate_segment(category, label="storage 类别")
    root = _storage_root()
    base = root / safe_category / tenant if tenant else root / safe_category
    candidate = resolve_storage_path(path)
    if candidate != base and not candidate.is_relative_to(base):
        raise ValidationError("storage 路径不能越出当前租户 storage 子树")
    return candidate


def resolve_storage_category_path(
    path: str | Path,
    category: str | Path,
) -> Path:
    """解析公共类别路径；用于回归样例等不属于租户私有子树的输入。"""
    safe_category = _validate_segment(category, label="storage 类别")
    root = _storage_root()
    base = root / safe_category
    candidate = resolve_storage_path(path)
    if candidate != base and not candidate.is_relative_to(base):
        raise ValidationError(f"storage 路径不能越出 storage/{safe_category}")
    return candidate


def resolve_storage_path(path: str | Path) -> Path:
    """解析既有 storage 路径；相对路径锚定 storage 根，结果不得越界。"""
    root = _storage_root()
    candidate = Path(path)
    if not candidate.is_absolute():
        # 兼容历史默认配置落库的 `storage/...` 相对路径；其他相对路径锚定 storage 根。
        process_candidate = Path.cwd() / candidate
        if process_candidate.resolve().is_relative_to(root):
            candidate = process_candidate
        else:
            candidate = root / candidate
    candidate = candidate.resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise ValidationError("storage 路径不能越出 storage 根")
    return candidate


def storage_display_path(path: str | Path) -> str:
    """把 canonical 路径转换回配置根下的展示路径，避免暴露服务器绝对路径。"""
    root = _storage_root()
    canonical = resolve_storage_path(path)
    relative = canonical.relative_to(root)
    return str(Path(settings.storage_root) / relative)
