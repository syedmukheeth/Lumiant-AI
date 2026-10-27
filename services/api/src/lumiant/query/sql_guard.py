"""Defense in depth: re-parse compiled SQL and refuse anything that is not a plain read of mapped tables.

The compiler never produces such SQL; this guard exists so that a future bug (or a future feature that
assembles SQL differently) cannot silently become a write, a system-table read or a file read.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from lumiant.core.errors import AppError

# Function nodes the compiler and analyses legitimately emit (sqlglot models AND/OR as functions too).
# Anything else (e.g. read_csv, getenv, duckdb_settings) is refused.
ALLOWED_FUNCTIONS: tuple[type[exp.Expression], ...] = (
    exp.And,
    exp.Or,
    exp.Sum,
    exp.Count,
    exp.Min,
    exp.Max,
    exp.Avg,
    exp.Coalesce,
    exp.Cast,
    exp.Nullif,
)
SYSTEM_SCHEMAS = {"information_schema", "pg_catalog", "sys", "system", "temp"}


class SqlGuardError(AppError):
    def __init__(self, reason: str) -> None:
        # The reason is for server logs and tests; the client only sees a generic message.
        super().__init__("query_rejected", "The query was rejected by a safety check.", 400)
        self.reason = reason


def check_sql(sql: str, dialect: str, allowed_tables: set[str]) -> None:
    try:
        statements = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except sqlglot.errors.ParseError as exc:
        raise SqlGuardError("unparseable") from exc
    if len(statements) != 1:
        raise SqlGuardError("multiple_statements")
    root = statements[0]
    if not isinstance(root, exp.Select):
        raise SqlGuardError(f"not_a_select:{type(root).__name__}")

    cte_names = {cte.alias_or_name.lower() for cte in root.find_all(exp.CTE)}
    nodes = list(root.walk())
    for node in nodes:
        if isinstance(node, exp.SetOperation):
            raise SqlGuardError("set_operation")
        if isinstance(node, (exp.Insert, exp.Update, exp.Delete, exp.Create, exp.Drop, exp.Command)):
            raise SqlGuardError(f"forbidden_node:{type(node).__name__}")
        if isinstance(node, exp.Func) and not isinstance(node, ALLOWED_FUNCTIONS):
            raise SqlGuardError(f"function_not_allowed:{node.sql_name()}")
    for node in nodes:
        if isinstance(node, exp.Table):
            name = node.name.lower()
            schema = (node.db or "").lower()
            if schema in SYSTEM_SCHEMAS or name.startswith(("duckdb_", "pg_", "sqlite_")):
                raise SqlGuardError(f"system_object:{schema}.{name}")
            qualified = f"{schema}.{name}" if schema else name
            if qualified not in allowed_tables and not (not schema and name in cte_names):
                raise SqlGuardError(f"table_not_allowed:{qualified}")
