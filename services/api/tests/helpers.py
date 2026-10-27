"""Test helpers."""

from __future__ import annotations

import atexit
import os
import uuid
from pathlib import Path

import duckdb
import duckdb_engine
import sqlalchemy as sa


def raw_duckdb(path: Path) -> duckdb.DuckDBPyConnection:
    """A plain read-only DuckDB connection for independent raw-SQL checks.

    DuckDB refuses a second in-process connection to the same file with a different configuration, and
    duckdb-engine sets `custom_user_agent`; we mirror it so these checks can run while the connector is open.
    """
    agent = f"duckdb_engine/{duckdb_engine.__version__}(sqlalchemy/{sa.__version__})"
    return duckdb.connect(str(path), read_only=True, config={"custom_user_agent": agent})


_PG_ADMIN_ENV = "LUMIANT_TEST_PG_ADMIN_URL"
_pg_created: list[str] = []


def _drop_pg_databases() -> None:
    admin_url = os.environ.get(_PG_ADMIN_ENV)
    if not admin_url or not _pg_created:
        return
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        for name in _pg_created:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    engine.dispose()


atexit.register(_drop_pg_databases)


def app_db_url(sqlite_path: Path) -> str:
    """URL for a test's application (audit) database.

    SQLite at `sqlite_path` by default. When LUMIANT_TEST_PG_ADMIN_URL is set (a PostgreSQL URL with
    CREATEDB rights, e.g. postgresql+psycopg://user:pw@localhost/postgres) a fresh, uniquely named PostgreSQL
    database is created instead, so the same suites run unchanged against PostgreSQL.
    """
    admin_url = os.environ.get(_PG_ADMIN_ENV)
    if not admin_url:
        return f"sqlite:///{sqlite_path.as_posix()}"
    name = f"lumiant_t_{uuid.uuid4().hex[:16]}"
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    engine.dispose()
    _pg_created.append(name)
    return sa.engine.make_url(admin_url).set(database=name).render_as_string(hide_password=False)
