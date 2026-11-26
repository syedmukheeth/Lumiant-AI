"""Copy a generated synthetic warehouse (DuckDB file) into another SQL database.

For connector conformance tests and demos only: it writes, so it never runs against a customer system. Names keep
their exact case, decimals stay DECIMAL(p, s), so the same tenant mapping works on the copy.

    uv run lumiant-synthetic copy --tenant demo-alpha --to "postgresql+psycopg://user:pw@localhost/lumiant_demo"
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb
import duckdb_engine
import sqlalchemy as sa

_DECIMAL = re.compile(r"DECIMAL\((\d+),\s*(\d+)\)")


def _type(duck_type: str) -> sa.types.TypeEngine[Any]:
    t = duck_type.upper()
    if m := _DECIMAL.match(t):
        return sa.Numeric(int(m.group(1)), int(m.group(2)), asdecimal=True)
    if t in ("INTEGER", "INT", "SMALLINT", "TINYINT"):
        return sa.Integer()
    if t in ("BIGINT", "HUGEINT", "UBIGINT"):
        return sa.BigInteger()
    if t in ("DOUBLE", "FLOAT", "REAL"):
        return sa.Float()
    if t == "DATE":
        return sa.Date()
    if t.startswith("TIMESTAMP"):
        return sa.DateTime(timezone="TIME ZONE" in t)
    if t == "BOOLEAN":
        return sa.Boolean()
    return sa.Text()


def copy_duckdb(source: Path, target_url: str, *, chunk: int = 5000) -> dict[str, int]:
    """Create every table of `source` in the target and copy its rows. Returns rows copied per table."""
    # Same configuration as the app's connector (duckdb-engine sets a user agent): DuckDB refuses a second
    # in-process connection to one file with a different configuration.
    agent = f"duckdb_engine/{duckdb_engine.__version__}(sqlalchemy/{sa.__version__})"
    src = duckdb.connect(str(source), read_only=True, config={"custom_user_agent": agent})
    engine = sa.create_engine(target_url)
    copied: dict[str, int] = {}
    try:
        names = [
            r[0]
            for r in src.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' ORDER BY 1"
            ).fetchall()
        ]
        md = sa.MetaData()
        tables: dict[str, sa.Table] = {}
        for name in names:
            cols = src.execute(f'DESCRIBE "{name}"').fetchall()
            tables[name] = sa.Table(
                name, md, *(sa.Column(c[0], _type(str(c[1])), quote=True) for c in cols), quote=True
            )
        md.drop_all(engine)
        md.create_all(engine)
        with engine.begin() as conn:
            for name, table in tables.items():
                cursor = src.execute(f'SELECT * FROM "{name}"')  # noqa: S608 (names from the generated file's catalog)
                keys = [d[0] for d in cursor.description or []]
                total = 0
                while batch := cursor.fetchmany(chunk):
                    conn.execute(table.insert(), [dict(zip(keys, row, strict=True)) for row in batch])
                    total += len(batch)
                copied[name] = total
    finally:
        src.close()
        engine.dispose()
    return copied
