"""Synthetic data: determinism and internal consistency, checked with raw SQL on the physical tables."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pytest

from lumiant.synthetic.generator import INJECTION_TEXT, Generator
from lumiant.synthetic.profiles import PROFILES
from lumiant.tenancy.registry import TenantRegistry
from tests.helpers import raw_duckdb


@pytest.fixture
def alpha(alpha_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    con = raw_duckdb(alpha_db)
    yield con
    con.close()


@pytest.fixture
def beta(beta_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    con = raw_duckdb(beta_db)
    yield con
    con.close()


def scenarios(con: duckdb.DuckDBPyConnection) -> dict[str, list[list[str]]]:
    row = con.execute("SELECT value FROM _dataset_info WHERE key = 'scenarios'").fetchone()
    assert row is not None
    result: dict[str, list[list[str]]] = json.loads(row[0])
    return result


def test_generation_is_deterministic() -> None:
    kwargs = {"as_of": date(2026, 10, 1), "n_items": 40, "months": 6}
    a = Generator(PROFILES["demo-alpha"], **kwargs).run()  # type: ignore[arg-type]
    b = Generator(PROFILES["demo-alpha"], **kwargs).run()  # type: ignore[arg-type]
    c = Generator(PROFILES["demo-alpha"], seed=1, **kwargs).run()  # type: ignore[arg-type]
    assert a.tables == b.tables
    assert a.scenarios == b.scenarios
    assert a.tables["inventory_transaction"] != c.tables["inventory_transaction"]


def test_profiles_match_tenant_config(registry: TenantRegistry) -> None:
    for tenant_id, profile in PROFILES.items():
        cfg = registry.get(tenant_id)
        assert [w.id for w in profile.warehouses] == [w.id for w in cfg.warehouses]
        assert {(w.id, w.department) for w in profile.warehouses} == {(w.id, w.department) for w in cfg.warehouses}
        assert [d for d, _ in profile.departments] == [d.id for d in cfg.departments]


def test_dataset_is_labelled_synthetic(alpha: duckdb.DuckDBPyConnection) -> None:
    row = alpha.execute("SELECT value FROM _dataset_info WHERE key = 'synthetic'").fetchone()
    assert row == ("true",)


def test_balances_equal_sum_of_movements(alpha: duckdb.DuckDBPyConnection) -> None:
    mismatches = alpha.execute(
        """
        WITH mv AS (
            SELECT MATNR, WERKS, LGORT, CHARG, SUM(MENGE) AS qty
            FROM ZV_MOVEMENT GROUP BY ALL HAVING SUM(MENGE) <> 0
        )
        SELECT count(*) FROM mv FULL OUTER JOIN ZV_STOCK s
          ON mv.MATNR = s.MATNR AND mv.WERKS = s.WERKS AND mv.LGORT = s.LGORT
         AND mv.CHARG IS NOT DISTINCT FROM s.CHARG
        WHERE mv.qty IS DISTINCT FROM s.LABST
        """
    ).fetchone()
    assert mismatches == (0,)


def test_beta_balances_equal_sum_of_movements(beta: duckdb.DuckDBPyConnection) -> None:
    mismatches = beta.execute(
        """
        WITH mv AS (
            SELECT item_id, warehouse_code, bin_code, lot_number, SUM(qty) AS qty
            FROM inv.stock_movements GROUP BY ALL HAVING SUM(qty) <> 0
        )
        SELECT count(*) FROM mv FULL OUTER JOIN inv.stock_on_hand s
          ON mv.item_id = s.item_id AND mv.warehouse_code = s.warehouse_code AND mv.bin_code = s.bin_code
         AND mv.lot_number IS NOT DISTINCT FROM s.lot_number
        WHERE mv.qty IS DISTINCT FROM s.qty_on_hand
        """
    ).fetchone()
    assert mismatches == (0,)


def test_running_lot_balances_never_negative(alpha: duckdb.DuckDBPyConnection) -> None:
    negative = alpha.execute(
        """
        SELECT count(*) FROM (
            SELECT SUM(MENGE) OVER (PARTITION BY MATNR, WERKS, LGORT, CHARG ORDER BY MBLNR) AS running
            FROM ZV_MOVEMENT
        ) WHERE running < 0
        """
    ).fetchone()
    assert negative == (0,)
    assert alpha.execute("SELECT count(*) FROM ZV_STOCK WHERE LABST <= 0").fetchone() == (0,)


def test_referential_integrity(alpha: duckdb.DuckDBPyConnection) -> None:
    checks = {
        "stock item": "SELECT count(*) FROM ZV_STOCK s LEFT JOIN ZV_MATERIAL m USING (MATNR) WHERE m.MATNR IS NULL",
        "stock plant": "SELECT count(*) FROM ZV_STOCK s LEFT JOIN ZV_PLANT p USING (WERKS) WHERE p.WERKS IS NULL",
        "stock batch": (
            "SELECT count(*) FROM ZV_STOCK s LEFT JOIN ZV_BATCH b USING (CHARG) "
            "WHERE s.CHARG IS NOT NULL AND b.CHARG IS NULL"
        ),
        "policy item": "SELECT count(*) FROM ZV_REORDER r LEFT JOIN ZV_MATERIAL m USING (MATNR) WHERE m.MATNR IS NULL",
    }
    for name, sql in checks.items():
        assert alpha.execute(sql).fetchone() == (0,), name


def test_join_keys_are_unique(alpha: duckdb.DuckDBPyConnection) -> None:
    for sql in (
        "SELECT MATNR FROM ZV_MATERIAL GROUP BY MATNR HAVING count(*) > 1",
        "SELECT WERKS FROM ZV_PLANT GROUP BY WERKS HAVING count(*) > 1",
        "SELECT MATNR, WERKS FROM ZV_REORDER GROUP BY ALL HAVING count(*) > 1",
        "SELECT CHARG FROM ZV_BATCH GROUP BY CHARG HAVING count(*) > 1",
    ):
        assert alpha.execute(sql).fetchall() == [], sql


def test_valuation_price_is_uniform_per_item_warehouse(alpha: duckdb.DuckDBPyConnection) -> None:
    rows = alpha.execute("SELECT MATNR, WERKS FROM ZV_STOCK GROUP BY ALL HAVING count(DISTINCT VERPR) > 1").fetchall()
    assert rows == []


def test_planted_scenarios_present(alpha: duckdb.DuckDBPyConnection) -> None:
    sc = scenarios(alpha)
    for key in (
        "below_reorder",
        "zero_stock_with_policy",
        "dormant",
        "missing_policy",
        "missing_valuation_price",
        "invalid_item_codes",
        "prompt_injection_items",
    ):
        assert sc[key], key


def test_zero_stock_scenario_matches_tables(alpha: duckdb.DuckDBPyConnection) -> None:
    for item, wh in scenarios(alpha)["zero_stock_with_policy"]:
        assert alpha.execute("SELECT count(*) FROM ZV_STOCK WHERE MATNR=? AND WERKS=?", [item, wh]).fetchone() == (0,)
        assert alpha.execute("SELECT count(*) FROM ZV_REORDER WHERE MATNR=? AND WERKS=?", [item, wh]).fetchone() == (1,)


def test_below_reorder_scenario_matches_tables(alpha: duckdb.DuckDBPyConnection) -> None:
    for item, wh in scenarios(alpha)["below_reorder"]:
        row = alpha.execute(
            """SELECT coalesce((SELECT SUM(LABST) FROM ZV_STOCK WHERE MATNR=? AND WERKS=?), 0) < MINBE
               FROM ZV_REORDER WHERE MATNR=? AND WERKS=?""",
            [item, wh, item, wh],
        ).fetchone()
        assert row == (True,)


def test_missing_valuation_scenario_matches_tables(alpha: duckdb.DuckDBPyConnection) -> None:
    for item, wh in scenarios(alpha)["missing_valuation_price"]:
        nulls = alpha.execute(
            "SELECT count(*) FROM ZV_STOCK WHERE MATNR=? AND WERKS=? AND VERPR IS NOT NULL", [item, wh]
        ).fetchone()
        assert nulls == (0,)


def test_prompt_injection_item_planted(alpha: duckdb.DuckDBPyConnection) -> None:
    (item,) = scenarios(alpha)["prompt_injection_items"][0]
    assert alpha.execute("SELECT MAKTX FROM ZV_MATERIAL WHERE MATNR=?", [item]).fetchone() == (INJECTION_TEXT,)


def test_beta_has_two_currencies_in_schema(beta: duckdb.DuckDBPyConnection) -> None:
    currencies = {r[0] for r in beta.execute("SELECT DISTINCT currency_code FROM inv.stock_on_hand").fetchall()}
    assert currencies == {"EUR", "GBP"}


def test_decimal_types_preserved(alpha: duckdb.DuckDBPyConnection) -> None:
    types = dict(
        alpha.execute(
            "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'ZV_STOCK'"
        ).fetchall()
    )
    assert types["LABST"] == "DECIMAL(18,4)"
    assert types["VERPR"] == "DECIMAL(18,4)"
