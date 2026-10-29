# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""initial schema - all 14 tables

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-04
"""
from __future__ import annotations

from alembic import op

from app.core.config import settings
from app.models import Base

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Use SQLAlchemy metadata to create all tables at the current schema.
    # Subsequent migrations will diff against this baseline using op.* primitives.
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    # Drop everything we created in upgrade(). Future down-migrations need
    # to diff against this baseline (we don't track per-table ownership here
    # since this is the initial commit).
    Base.metadata.drop_all(bind=bind)
