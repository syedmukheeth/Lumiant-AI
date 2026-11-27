"""Test a database connection before it is configured (V1 Connect step, docs/05-plan/PRODUCT_V3_PLAN.md §3.3).

Opens the source read-only, checks it answers, reports whether the account itself can write (it should not), and
lists the tables and views it can see. Metadata only: no row values are read. The URL is used once and never stored,
logged or echoed back (credentials are masked in every message).
"""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa

from lumiant.connectors.base import ConnectorError
from lumiant.connectors.sql_connector import GUARD_DIALECTS, SqlConnector

log = logging.getLogger("lumiant.connectors.probe")
MAX_OBJECTS = 300

# Tables the account may write to, from the database's own privilege catalog (no write is attempted).
_WRITABLE = {
    "postgresql": sa.text(
        "SELECT count(*) FROM information_schema.table_privileges "
        "WHERE privilege_type IN ('INSERT','UPDATE','DELETE','TRUNCATE') "
        "AND grantee IN (current_user, 'PUBLIC') "
        "AND table_schema NOT IN ('pg_catalog','information_schema')"
    ),
    "mssql": sa.text(
        "SELECT count(*) FROM sys.objects o "
        "CROSS APPLY fn_my_permissions(QUOTENAME(SCHEMA_NAME(o.schema_id)) + '.' + QUOTENAME(o.name), 'OBJECT') p "
        "WHERE o.type IN ('U','V') AND p.permission_name IN ('INSERT','UPDATE','DELETE')"
    ),
    "mysql": sa.text(
        "SELECT count(*) FROM information_schema.user_privileges "
        "WHERE privilege_type IN ('INSERT','UPDATE','DELETE') AND grantee = CONCAT(\"'\", "
        "SUBSTRING_INDEX(CURRENT_USER(), '@', 1), \"'@'\", SUBSTRING_INDEX(CURRENT_USER(), '@', -1), \"'\")"
    ),
}


def _read_only(connector: SqlConnector) -> dict[str, Any]:
    if connector.backend == "sqlite":
        return {"status": "proved", "detail": "Opened in read-only mode by the file system driver."}
    query = _WRITABLE.get(connector.backend)
    if query is None:
        return {"status": "not_checked", "detail": "Use an account that can only read approved views."}
    try:
        with connector._engine.connect() as conn:
            writable = int(conn.execute(query).scalar() or 0)
    except sa.exc.DBAPIError:
        return {"status": "not_checked", "detail": "The account's privileges could not be read."}
    if writable:
        return {
            "status": "writable",
            "detail": (
                f"This account may change {writable} table(s). Lumiant only reads and opens read-only sessions, "
                "but connect with an account that can only read approved views."
            ),
        }
    return {"status": "proved", "detail": "The account has no insert, update or delete rights."}


def probe(url: str, *, allow_sqlite: bool) -> dict[str, Any]:
    """Result of testing `url`. Never raises for source problems; the URL is never part of the result."""
    try:
        backend = sa.make_url(url).get_backend_name()
    except (sa.exc.ArgumentError, ValueError):
        return {"ok": False, "code": "invalid_url", "message": "That is not a database URL (dialect+driver://...)."}
    if backend not in GUARD_DIALECTS or (backend == "sqlite" and not allow_sqlite):
        supported = ", ".join(b for b in GUARD_DIALECTS if b != "sqlite")
        return {"ok": False, "code": "unsupported_source", "message": f"Supported databases: {supported}."}
    try:
        connector = SqlConnector(url)
    except (ConnectorError, sa.exc.ArgumentError, ModuleNotFoundError):
        return {
            "ok": False,
            "code": "driver_missing",
            "message": f"The {backend} driver is not installed on the server.",
        }
    try:
        if not connector.health():
            return {
                "ok": False,
                "code": "source_unavailable",
                "message": "The database did not answer. Check host, port, network access and credentials.",
            }
        objects = connector.list_objects()
        return {
            "ok": True,
            "backend": backend,
            "read_only": _read_only(connector),
            "object_count": len(objects),
            "objects": [{"schema": o.schema, "name": o.name, "kind": o.kind} for o in objects[:MAX_OBJECTS]],
            "truncated": len(objects) > MAX_OBJECTS,
        }
    except (ConnectorError, sa.exc.DBAPIError) as exc:
        log.warning("probe_failed", extra={"backend": backend, "error_type": type(exc).__name__})
        return {"ok": False, "code": "source_unavailable", "message": "Connected, but the catalog could not be read."}
    finally:
        connector.dispose()


def suggest_for_url(url: str, *, allow_sqlite: bool) -> dict[str, Any]:
    """Mapping suggestions for a source that is not configured yet (names only; the URL is used once)."""
    from lumiant.mapping.suggest import read_tables, suggest

    checked = probe(url, allow_sqlite=allow_sqlite)
    if not checked["ok"]:
        return checked
    connector = SqlConnector(url)
    try:
        return {"ok": True, **suggest(read_tables(connector))}
    except (ConnectorError, sa.exc.DBAPIError):
        return {"ok": False, "code": "source_unavailable", "message": "The table and column names could not be read."}
    finally:
        connector.dispose()
