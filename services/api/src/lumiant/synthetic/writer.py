"""Writes a SyntheticDataset into a DuckDB file using the tenant's physical mapping."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import duckdb

from lumiant.canonical.catalog import FieldType
from lumiant.mapping.resolver import SourceObject, TenantMapping
from lumiant.synthetic.generator import GENERATOR_VERSION, SyntheticDataset
from lumiant.tenancy.models import TenantConfig

DUCKDB_TYPES = {
    FieldType.STRING: "VARCHAR",
    FieldType.INTEGER: "INTEGER",
    FieldType.DECIMAL: "DECIMAL(18,4)",
    FieldType.DATE: "DATE",
    FieldType.DATETIME: "TIMESTAMP",
    FieldType.BOOLEAN: "BOOLEAN",
}
NULL = r"\N"


class WriterError(Exception):
    pass


def _q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _qualified(src: SourceObject) -> str:
    return f"{_q(src.schema)}.{_q(src.name)}" if src.schema else _q(src.name)


def _cell(value: object) -> str:
    if value is None:
        return NULL
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def write_duckdb(dataset: SyntheticDataset, tenant: TenantConfig, target: Path) -> Path:
    """Create `target` atomically. Fails if the file is open elsewhere (stop the API first)."""
    mapping = TenantMapping(tenant)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_db = target.with_suffix(".tmp.duckdb")
    for leftover in (tmp_db, tmp_db.with_suffix(".duckdb.wal")):
        leftover.unlink(missing_ok=True)

    con = duckdb.connect(str(tmp_db))
    try:
        with tempfile.TemporaryDirectory(prefix="lumiant-synth-") as scratch:
            for ds_name, ds_map in tenant.datasets.items():
                rows = dataset.tables.get(ds_name)
                if rows is None:
                    raise WriterError(f"generator produced no '{ds_name}' records")
                _write_table(con, mapping, ds_name, ds_map.source, rows, Path(scratch))
        _write_metadata(con, dataset, tenant)
        con.execute("CHECKPOINT")
    finally:
        con.close()
    try:
        os.replace(tmp_db, target)
    except PermissionError as exc:
        tmp_db.unlink(missing_ok=True)
        raise WriterError(f"{target} is in use — stop the API before regenerating synthetic data") from exc
    return target


def _write_table(
    con: duckdb.DuckDBPyConnection,
    mapping: TenantMapping,
    dataset: str,
    source: str,
    rows: list[dict[str, object]],
    scratch: Path,
) -> None:
    src = SourceObject.parse(source)
    fields = mapping.fields(dataset)
    columns: dict[str, list[str]] = {}  # physical column -> canonical fields feeding it
    for fname in fields:
        if fields[fname].computed:
            continue
        columns.setdefault(mapping.physical_column(dataset, fname), []).append(fname)
    if src.schema:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {_q(src.schema)}")
    ddl = ", ".join(f"{_q(col)} {DUCKDB_TYPES[fields[names[0]].type]}" for col, names in columns.items())
    con.execute(f"CREATE TABLE {_qualified(src)} ({ddl})")

    csv_path = scratch / f"{dataset}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(list(columns))
        for row in rows:
            out = []
            for names in columns.values():
                values = {repr(row.get(n)) for n in names}
                if len(values) > 1:
                    raise WriterError(f"{dataset}: fields {names} share a column but differ")
                out.append(_cell(row.get(names[0])))
            writer.writerow(out)
    con.execute(
        f"COPY {_qualified(src)} FROM ? (HEADER true, DELIMITER ',', QUOTE '\"', NULLSTR ?)",
        [str(csv_path), NULL],
    )


def _write_metadata(con: duckdb.DuckDBPyConnection, dataset: SyntheticDataset, tenant: TenantConfig) -> None:
    con.execute("CREATE TABLE _dataset_info (key VARCHAR, value VARCHAR)")
    info = {
        "synthetic": "true",
        "tenant_id": dataset.tenant_id,
        "seed": str(dataset.seed),
        "as_of": dataset.as_of.isoformat(),
        "generator_version": GENERATOR_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "scenarios": json.dumps(dataset.scenarios),
    }
    con.executemany("INSERT INTO _dataset_info VALUES (?, ?)", list(info.items()))
    if tenant.freshness is not None:
        src = SourceObject.parse(tenant.freshness.object)
        if src.schema:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {_q(src.schema)}")
        con.execute(f"CREATE TABLE {_qualified(src)} (dataset VARCHAR, {_q(tenant.freshness.column)} TIMESTAMP)")
        extracted = datetime.now(UTC).replace(tzinfo=None, microsecond=0)
        con.executemany(
            # Identifiers come from the validated tenant config and are quoted; values are bound.
            f"INSERT INTO {_qualified(src)} VALUES (?, ?)",  # noqa: S608
            [(name, extracted) for name in tenant.datasets],
        )
