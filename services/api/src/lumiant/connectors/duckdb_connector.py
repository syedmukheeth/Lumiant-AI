"""DuckDB connector for the synthetic demo warehouses. Opened read-only at the database level."""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Dialect
from sqlalchemy.pool import QueuePool

from lumiant.connectors.base import ColumnInfo, ConnectorError, ObjectInfo, RawResult

log = logging.getLogger("lumiant.connectors.duckdb")


class DuckDBConnector:
    dialect_name = "duckdb"

    def __init__(self, path: Path, *, pool_size: int = 4) -> None:
        self.path = path
        self._engine = sa.create_engine(
            f"duckdb:///{path.as_posix()}",
            connect_args={"read_only": True},
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=2,
            pool_timeout=10,
        )

    @property
    def dialect(self) -> Dialect:
        return self._engine.dialect

    def _connect(self) -> sa.Connection:
        if not self.path.is_file():
            raise ConnectorError("source_unavailable")
        try:
            return self._engine.connect()
        except sa.exc.DBAPIError as exc:
            log.warning("connect_failed", extra={"error_type": type(exc.orig).__name__})
            raise ConnectorError("source_unavailable") from exc

    def health(self) -> bool:
        try:
            with self._connect() as conn:
                return conn.execute(sa.select(sa.literal(1))).scalar() == 1
        except (ConnectorError, sa.exc.DBAPIError):
            return False

    def has_table(self, schema: str | None, name: str) -> bool:
        with self._connect() as conn:
            return bool(sa.inspect(conn).has_table(name, schema=schema))

    def list_objects(self) -> list[ObjectInfo]:
        objects: list[ObjectInfo] = []
        with self._connect() as conn:
            insp = sa.inspect(conn)
            for schema in insp.get_schema_names():
                if schema in ("information_schema", "pg_catalog"):
                    continue
                objects += [ObjectInfo(schema, n, "table") for n in insp.get_table_names(schema=schema)]
                objects += [ObjectInfo(schema, n, "view") for n in insp.get_view_names(schema=schema)]
        return objects

    def describe(self, schema: str | None, name: str) -> list[ColumnInfo]:
        with self._connect() as conn:
            cols = sa.inspect(conn).get_columns(name, schema=schema)
        return [ColumnInfo(c["name"], str(c["type"]), bool(c.get("nullable", True))) for c in cols]

    def execute(self, stmt: sa.Select[Any], *, fetch_limit: int, timeout_s: float) -> RawResult:
        with self._connect() as conn:
            driver = conn.connection.driver_connection
            fired = threading.Event()

            def _interrupt() -> None:
                fired.set()
                driver.interrupt()  # type: ignore[union-attr]

            timer = threading.Timer(timeout_s, _interrupt)
            timer.daemon = True
            started = time.perf_counter()
            timer.start()
            try:
                result = conn.execute(stmt)
                columns = list(result.keys())
                rows = [tuple(r) for r in result.fetchmany(fetch_limit)]
                result.close()
            except sa.exc.DBAPIError as exc:
                conn.rollback()
                code = "query_timeout" if fired.is_set() else "query_failed"
                log.warning("query_failed", extra={"code": code, "error_type": type(exc.orig).__name__})
                raise ConnectorError(code) from exc
            finally:
                timer.cancel()
            conn.rollback()
            return RawResult(columns, rows, round((time.perf_counter() - started) * 1000, 1))

    def dispose(self) -> None:
        self._engine.dispose()
