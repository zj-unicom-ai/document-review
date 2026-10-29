# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Domain exceptions."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""

    code: str = "domain_error"
    http_status: int = 400


class NotFoundError(DomainError):
    code = "not_found"
    http_status = 404


class ValidationError(DomainError):
    code = "validation_error"
    http_status = 422


class ConflictError(DomainError):
    code = "conflict"
    http_status = 409


class ImmutableError(DomainError):
    code = "immutable"
    http_status = 403


class UnauthorizedError(DomainError):
    code = "unauthorized"
    http_status = 401


class ForbiddenError(DomainError):
    code = "forbidden"
    http_status = 403
