# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Import all models here so Alembic autogenerate can pick them up."""

from app.models.base import (
    AuditMixin,
    Base,
    IdMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
)
from app.models.classification import Classification
from app.models.concept import Concept
from app.models.document_template import DocumentTemplate
from app.models.external_resource import ExternalResource
from app.models.operator import Operator
from app.models.review_run import ReviewRun, RuleExecution
from app.models.rule import Rule, RuleChangeLog
from app.models.rule_set import RuleSet, RuleSetItem
from app.models.structure_profile import StructureProfile
from app.models.tenant import Tenant

__all__ = [
    "AuditMixin",
    "Base",
    "Classification",
    "Concept",
    "DocumentTemplate",
    "ExternalResource",
    "IdMixin",
    "Operator",
    "ReviewRun",
    "Rule",
    "RuleChangeLog",
    "RuleExecution",
    "RuleSet",
    "RuleSetItem",
    "SoftDeleteMixin",
    "StructureProfile",
    "Tenant",
    "TenantMixin",
    "TimestampMixin",
]
