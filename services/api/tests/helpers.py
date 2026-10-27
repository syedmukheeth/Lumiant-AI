"""Test helpers."""

from __future__ import annotations

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
