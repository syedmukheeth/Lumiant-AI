"""V2: mapping suggestions from names match the real mappings of every demo tenant, and the validation harness catches
duplicate keys, orphans and missing required values (docs/AI_SCHEMA_DISCOVERY.md §9)."""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa

from lumiant.admin.validation import run_validation
from lumiant.connectors.duckdb_connector import DuckDBConnector
from lumiant.connectors.probe import suggest_for_url
from lumiant.connectors.sql_connector import SqlConnector
from lumiant.mapping.resolver import TenantMapping
from lumiant.mapping.suggest import read_tables, suggest
from lumiant.synthetic.copy import copy_duckdb
from lumiant.tenancy.registry import TenantRegistry

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("tenant", ["demo-alpha", "demo-beta", "demo-gamma", "demo-delta"])
def test_suggestions_agree_with_the_real_mapping(tenant: str, registry: TenantRegistry, data_dir: Path) -> None:
    """Four naming styles: SAP field names, modern names in a schema, prepared views, a manufacturing layout."""
    connector = DuckDBConnector(data_dir / "data" / "synthetic" / f"{tenant}.duckdb")
    try:
        result = suggest(read_tables(connector))
    finally:
        connector.dispose()
    cfg = registry.get(tenant)
    compared = 0
    for row in result["datasets"]:
        truth = cfg.datasets.get(row["dataset"])
        if truth is None:
            continue
        compared += 1
        assert row["source"] == truth.source, row["dataset"]
        assert not row["missing_required"], row["dataset"]
        for canonical, column in row["fields"].items():
            if canonical in truth.fields:
                assert truth.fields[canonical] == column, (row["dataset"], canonical)
    assert compared >= 3  # gamma (SAP extract twin) maps three core datasets
    assert result["yaml"].startswith("# Draft mapping")


def test_names_only_no_values(data_dir: Path) -> None:
    connector = DuckDBConnector(data_dir / "data" / "synthetic" / "demo-alpha.duckdb")
    try:
        text = str(suggest(read_tables(connector)))
    finally:
        connector.dispose()
    assert "1100" not in text  # a warehouse id from the data never appears: only table and column names are read


@pytest.fixture
def broken_copy(alpha_db: Path, tmp_path: Path) -> str:
    """A writable copy of the alpha warehouse with one of each structural problem planted."""
    target = tmp_path / "broken.sqlite"
    url = f"sqlite:///{target.as_posix()}"
    copy_duckdb(alpha_db, url)
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text('INSERT INTO "ZV_MATERIAL" SELECT * FROM "ZV_MATERIAL" LIMIT 1'))  # duplicate item
        conn.execute(sa.text('UPDATE "ZV_STOCK" SET "MATNR" = \'NO-SUCH-ITEM\' WHERE rowid = 1'))  # orphan
        conn.execute(sa.text('UPDATE "ZV_STOCK" SET "LABST" = NULL WHERE rowid = 2'))  # required value missing
    engine.dispose()
    return url


def test_validation_finds_planted_problems(broken_copy: str, registry: TenantRegistry, alpha_db: Path) -> None:
    mapping = TenantMapping(registry.get("demo-alpha"))
    clean = DuckDBConnector(alpha_db)
    try:
        assert all(c["status"] == "ok" for c in run_validation(mapping, clean))
    finally:
        clean.dispose()
    connector = SqlConnector(broken_copy)
    try:
        checks = {c["id"]: c for c in run_validation(mapping, connector)}
    finally:
        connector.dispose()
    assert checks["unique_item"]["count"] == 1
    assert checks["orphan_stock_balance_item_id"]["count"] == 1
    assert checks["required_stock_balance"]["count"] == 1
    assert checks["unique_warehouse"]["status"] == "ok"


def test_suggest_for_a_url(alpha_db: Path, tmp_path: Path) -> None:
    target = tmp_path / "alpha.sqlite"
    copy_duckdb(alpha_db, f"sqlite:///{target.as_posix()}")
    result = suggest_for_url(f"sqlite:///{target.as_posix()}", allow_sqlite=True)
    assert result["ok"] is True
    stock = next(d for d in result["datasets"] if d["dataset"] == "stock_balance")
    assert stock["source"] == "ZV_STOCK"
    assert stock["confidence"] == "high"
    refused = suggest_for_url("firebird://u:p@h/db", allow_sqlite=True)
    assert refused["ok"] is False
