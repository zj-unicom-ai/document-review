# Copyright (c) 2026 Document Review Contributors
# SPDX-License-Identifier: MIT

"""Alembic environment - sync URL pulled directly from app settings.

We don't go through config.set_main_option because configparser interprets %
as interpolation and our URL-encoded password contains % characters.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models
from alembic import context

# Import settings + all models so Base.metadata is fully populated
from app.core.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _make_engine():
    """Build a sync engine using the runtime URL (handles % in passwords)."""
    cfg = config.get_section(config.config_ini_section, {}) or {}
    cfg["sqlalchemy.url"] = settings.sync_database_url
    return engine_from_config(cfg, prefix="sqlalchemy.", poolclass=pool.NullPool)


def run_migrations_offline() -> None:
    context.configure(
        url=settings.sync_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = _make_engine()
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
