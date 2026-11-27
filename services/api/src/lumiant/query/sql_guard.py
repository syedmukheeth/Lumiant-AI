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
    exp.Lower,  # `contains` on dialects without ILIKE (SQL Server, Oracle) compiles to lower(x) LIKE lower(?)
    exp.Case,  # value maps (mapping/resolver.py); sqlglot models each WHEN branch as If
    exp.If,
)
# Time buckets (compiler.DateBucket): one date-formatting function per dialect. Matched by exact type, so a subclass
# (CONCAT_WS under Concat) is not allowed along with its parent.
TIME_BUCKET_FUNCTIONS: frozenset[type[exp.Func]] = frozenset(
    {
        exp.TimeToStr,  # strftime (DuckDB, SQLite), to_char (PostgreSQL), DATE_FORMAT (MySQL)
        exp.ToChar,  # TO_CHAR (Oracle)
        exp.Convert,  # CONVERT(char(n), x, 126) (SQL Server)
        exp.Extract,  # quarter number: EXTRACT(QUARTER FROM x), DATEPART(quarter, x) on SQL Server
        exp.Concat,  # quarter label on MySQL, where || means OR
    }
)
# sqlglot wraps the date argument of SQLite strftime and MySQL DATE_FORMAT in this node; allowed only right there.
_PARSER_WRAPPERS: dict[type[exp.Func], type[exp.Func]] = {exp.TsOrDsToTimestamp: exp.TimeToStr}
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
        if isinstance(node, exp.Func) and not _function_allowed(node):
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


def _function_allowed(node: exp.Func) -> bool:
    if isinstance(node, ALLOWED_FUNCTIONS) or type(node) in TIME_BUCKET_FUNCTIONS:
        return True
    parent = _PARSER_WRAPPERS.get(type(node))
    return parent is not None and type(node.parent) is parent and node.arg_key == "this"
