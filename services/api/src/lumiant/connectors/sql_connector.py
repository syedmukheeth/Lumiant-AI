"""Read-only connector for SQL databases reached through SQLAlchemy (V1, docs/05-plan/PRODUCT_V3_PLAN.md §3.2).

Same contract as the DuckDB connector: it only executes SQLAlchemy `Select` objects built by the compiler or the named
analyses (there is no `execute(sql_string)`), caps rows, and cancels on timeout. Read-only is enforced by the database
first, then by the SQL guard:

- PostgreSQL: every session starts with `default_transaction_read_only=on`; the account should only SELECT approved
  views.
- SQL Server: the account must be a reader on approved views (`db_datareader` or SELECT grants);
  `ApplicationIntent=ReadOnly` can be set in the URL.
- MySQL: the account must hold SELECT only; every session runs `SET SESSION TRANSACTION READ ONLY`.
- SQLite: opened with `mode=ro` (development and tests only, never a customer source).

Only backends listed in `GUARD_DIALECTS` are accepted. "Supported" for a customer still requires the conformance suite
against that engine (`tests/integration/test_sql_connector.py`, 02-architecture/CONNECTORS.md).
"""

from __future__ import annotations

import logging
import threading
import time
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import Dialect

from lumiant.connectors.base import ColumnInfo, ConnectorError, ObjectInfo, RawResult

log = logging.getLogger("lumiant.connectors.sql")

# SQLAlchemy backend name -> sqlglot dialect used by the SQL guard
GUARD_DIALECTS = {
    "postgresql": "postgres",
    "mssql": "tsql",
    "mysql": "mysql",
    "oracle": "oracle",
    "sqlite": "sqlite",
}
_SYSTEM_SCHEMAS = frozenset({"information_schema", "pg_catalog", "pg_toast", "sys", "mysql", "performance_schema"})


def _read_only_url(url: sa.URL) -> sa.URL:
    if url.get_backend_name() != "sqlite":
        return url
    path = url.database or ""
    if not path or path == ":memory:":
        raise ConnectorError("source_unavailable")
    return url.set(database=f"file:{path}", query={**url.query, "mode": "ro", "uri": "true"})


class SqlConnector:
    def __init__(self, url: str, *, pool_size: int = 4) -> None:
        parsed = sa.make_url(url)
        backend = parsed.get_backend_name()
        if backend not in GUARD_DIALECTS:
            raise ConnectorError("unsupported_source")
        self.backend = backend
        self.dialect_name = GUARD_DIALECTS[backend]
        connect_args: dict[str, Any] = {}
        if backend == "postgresql":
            connect_args["options"] = "-c default_transaction_read_only=on"
        elif backend == "sqlite":
            connect_args["check_same_thread"] = False
        self._engine = sa.create_engine(
            _read_only_url(parsed),
            connect_args=connect_args,
            pool_size=pool_size,
            max_overflow=2,
            pool_timeout=10,
            pool_pre_ping=True,
        )
        if backend == "mysql":

            @sa.event.listens_for(self._engine, "connect")
            def _read_only(dbapi_conn: Any, _record: Any) -> None:
                cur = dbapi_conn.cursor()
                cur.execute("SET SESSION TRANSACTION READ ONLY")
                cur.close()

    @property
    def dialect(self) -> Dialect:
        return self._engine.dialect

    def _connect(self) -> sa.Connection:
        try:
            return self._engine.connect()
        except sa.exc.DBAPIError as exc:
            log.warning("connect_failed", extra={"backend": self.backend, "error_type": type(exc.orig).__name__})
            raise ConnectorError("source_unavailable") from exc

    def health(self) -> bool:
        try:
            with self._connect() as conn:
                return conn.execute(sa.select(sa.literal(1))).scalar() == 1
        except (ConnectorError, sa.exc.DBAPIError):
            return False

    def has_table(self, schema: str | None, name: str) -> bool:
        with self._connect() as conn:
            insp = sa.inspect(conn)
            return bool(insp.has_table(name, schema=schema)) or name in insp.get_view_names(schema=schema)

    def list_objects(self) -> list[ObjectInfo]:
        objects: list[ObjectInfo] = []
        with self._connect() as conn:
            insp = sa.inspect(conn)
            for schema in insp.get_schema_names():
                if schema in _SYSTEM_SCHEMAS or schema.startswith("pg_"):
                    continue
                objects += [ObjectInfo(schema, n, "table") for n in insp.get_table_names(schema=schema)]
                objects += [ObjectInfo(schema, n, "view") for n in insp.get_view_names(schema=schema)]
        return objects

    def describe(self, schema: str | None, name: str) -> list[ColumnInfo]:
        with self._connect() as conn:
            cols = sa.inspect(conn).get_columns(name, schema=schema)
        return [ColumnInfo(c["name"], str(c["type"]), bool(c.get("nullable", True))) for c in cols]

    def _cancel(self, driver: Any) -> None:
        for name in ("interrupt", "cancel"):  # sqlite3 / psycopg
            fn = getattr(driver, name, None)
            if callable(fn):
                fn()
                return

    def execute(self, stmt: sa.Select[Any], *, fetch_limit: int, timeout_s: float) -> RawResult:
        if not isinstance(stmt, sa.Select):
            raise ConnectorError("query_failed")
        with self._connect() as conn:
            if self.backend == "postgresql":  # server-side limit as well as the client-side cancel below
                conn.execute(sa.text(f"SET LOCAL statement_timeout = {int(timeout_s * 1000)}"))
            driver = conn.connection.driver_connection
            fired = threading.Event()

            def _interrupt() -> None:
                fired.set()
                self._cancel(driver)

            timer = threading.Timer(timeout_s, _interrupt)
            timer.daemon = True
            started = time.perf_counter()
            timer.start()
            try:
                result = conn.execute(stmt)
                columns = list(result.keys())
                rows = [tuple(_exact(v) for v in r) for r in result.fetchmany(fetch_limit)]
                result.close()
            except sa.exc.DBAPIError as exc:
                conn.rollback()
                code = "query_timeout" if fired.is_set() or _is_timeout(exc) else "query_failed"
                log.warning("query_failed", extra={"code": code, "error_type": type(exc.orig).__name__})
                raise ConnectorError(code) from exc
            finally:
                timer.cancel()
            conn.rollback()
            return RawResult(columns, rows, round((time.perf_counter() - started) * 1000, 1))

    def dispose(self) -> None:
        self._engine.dispose()


def _exact(value: Any) -> Any:
    """Money and quantities never leave a connector as float (SQLite stores decimals as REAL)."""
    return Decimal(repr(value)) if isinstance(value, float) else value


def _is_timeout(exc: sa.exc.DBAPIError) -> bool:
    text = str(exc.orig).lower()
    return "statement timeout" in text or "canceling statement" in text or "interrupted" in text
