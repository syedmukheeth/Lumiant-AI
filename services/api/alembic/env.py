"""Alembic environment. Logging is left to the application (no fileConfig)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import context

from lumiant.audit.store import Base
from lumiant.core.config import get_settings

config = context.config
url = config.get_main_option("sqlalchemy.url") or get_settings().app_db_url
target_metadata = Base.metadata


def run_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = sa.create_engine(url, poolclass=sa.pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
