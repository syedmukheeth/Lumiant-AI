"""M2 analyses over HTTP, reconciled against independent raw SQL / hand computation."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lumiant.core.config import Settings
from lumiant.main import create_app
from tests.helpers import app_db_url, raw_duckdb

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


@pytest.fixture(scope="module")
def client(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="m2-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("m2db") / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client: TestClient, user: str) -> TestClient:
    client.cookies.clear()
    assert client.post("/api/auth/dev-login", json={"username": user}, headers=CSRF).status_code == 200
    return client


def get(client: TestClient, url: str, **params: Any) -> Any:
    r = client.get(url, params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_excess_stock_matches_independent_sql(client: TestClient, alpha_db: Path) -> None:
    body = get(login(client, "alpha.admin"), "/api/analyses/excess-stock", limit=200)
    con = raw_duckdb(alpha_db)
    expected = con.execute(
        """
        WITH oh AS (SELECT s.MATNR, s.WERKS, SUM(s.LABST) q FROM ZV_STOCK s JOIN ZV_MATERIAL m USING (MATNR)
                    WHERE s.MEINS = m.MEINS GROUP BY ALL)
        SELECT r.MATNR, r.WERKS FROM ZV_REORDER r JOIN oh ON oh.MATNR = r.MATNR AND oh.WERKS = r.WERKS
        WHERE r.MABST IS NOT NULL AND oh.q > r.MABST
        """
    ).fetchall()
    con.close()
    assert {(r["item_id"], r["warehouse_id"]) for r in body["data"]} == {tuple(x) for x in expected}
    assert all(Decimal(r["on_hand"]) > Decimal(r["max_stock"]) for r in body["data"])
    assert all(Decimal(r["excess"]) == Decimal(r["on_hand"]) - Decimal(r["max_stock"]) for r in body["data"])


def test_dormant_matches_independent_sql(client: TestClient, alpha_db: Path) -> None:
    body = get(login(client, "alpha.admin"), "/api/analyses/dormant", days=180, limit=200)
    as_of = date.fromisoformat(body["summary"]["as_of"])
    con = raw_duckdb(alpha_db)
    expected = con.execute(
        """
        WITH oh AS (SELECT MATNR, WERKS, SUM(LABST) q FROM ZV_STOCK GROUP BY ALL HAVING SUM(LABST) > 0),
             li AS (SELECT MATNR, WERKS, MAX(BUDAT) d FROM ZV_MOVEMENT WHERE BWART = 'ISSUE' GROUP BY ALL)
        SELECT oh.MATNR, oh.WERKS FROM oh LEFT JOIN li USING (MATNR, WERKS)
        WHERE li.d IS NULL OR li.d < ?::DATE - INTERVAL 180 DAY
        """,
        [as_of.isoformat()],
    ).fetchall()
    con.close()
    assert body["summary"]["flagged"] == len(expected)
    if len(expected) <= 200:
        assert {(r["item_id"], r["warehouse_id"]) for r in body["data"]} == {tuple(x) for x in expected}
    for r in body["data"]:
        assert r["days_since_issue"] is None or r["days_since_issue"] > 180


def test_expiring_lots(client: TestClient, alpha_db: Path) -> None:
    body = get(login(client, "alpha.admin"), "/api/analyses/expiring-lots", days=60, limit=200)
    con = raw_duckdb(alpha_db)
    expected = con.execute(
        "SELECT count(*) FROM ZV_STOCK s JOIN ZV_BATCH b USING (CHARG) "
        "WHERE s.LABST > 0 AND b.VFDAT <= ?::DATE + INTERVAL 60 DAY",
        [body["provenance"]["parameters"]["as_of"]],
    ).fetchone()
    con.close()
    assert expected is not None
    assert len(body["data"]) == min(expected[0], 200)
    assert {r["status"] for r in body["data"]} <= {"expired", "expiring"}
    days = [r["days_to_expiry"] for r in body["data"]]
    assert days == sorted(days)
    assert body["summary"]["expired"] + body["summary"]["expiring"] == len(body["data"])


def test_data_quality_reports_planted_gaps(client: TestClient, alpha_db: Path) -> None:
    body = get(login(client, "alpha.admin"), "/api/analyses/data-quality")
    checks = {c["id"]: c for c in body["checks"]}
    con = raw_duckdb(alpha_db)
    row = con.execute("SELECT value FROM _dataset_info WHERE key='scenarios'").fetchone()
    con.close()
    assert row is not None
    scenarios = json.loads(row[0])
    assert checks["invalid_item_codes"]["count"] == len(scenarios["invalid_item_codes"])
    assert checks["pairs_without_policy"]["count"] == len(scenarios["missing_policy"])
    assert checks["missing_valuation_price"]["count"] >= len(scenarios["missing_valuation_price"])
    assert body["synthetic"] is True


@pytest.mark.security
def test_cost_analyses_forbidden_without_cost_permission(client: TestClient) -> None:
    login(client, "alpha.analyst")
    assert client.get("/api/analyses/abc", params={"a": "0.8", "b": "0.95"}).status_code == 403
    r = client.get("/api/analyses/cost-comparison", params={"item_id": "x", "warehouse_id": "3100"})
    assert r.status_code == 403
    checks = {c["id"]: c for c in get(client, "/api/analyses/data-quality")["checks"]}
    assert checks["missing_valuation_price"]["status"] == "restricted"


@pytest.mark.security
def test_scoped_user_cannot_cost_out_of_scope_pair(client: TestClient, alpha_db: Path) -> None:
    con = raw_duckdb(alpha_db)
    row = con.execute("SELECT MATNR, WERKS FROM ZV_MOVEMENT WHERE WERKS LIKE '3%' LIMIT 1").fetchone()
    con.close()
    assert row is not None
    login(client, "alpha.north_manager")
    r = client.get("/api/analyses/cost-comparison", params={"item_id": row[0], "warehouse_id": row[1]})
    assert r.status_code == 403


def test_cost_comparison_reconciles_with_source_valuation(client: TestClient, alpha_db: Path) -> None:
    con = raw_duckdb(alpha_db)
    pairs = con.execute(
        "SELECT MATNR, WERKS FROM ZV_STOCK WHERE VERPR IS NOT NULL GROUP BY ALL ORDER BY SUM(LABST) DESC LIMIT 15"
    ).fetchall()
    con.close()
    login(client, "alpha.admin")
    matches = 0
    for item, wh in pairs:
        body = get(client, "/api/analyses/cost-comparison", item_id=item, warehouse_id=wh)
        assert not body["errors"], body["errors"]
        methods = body["methods"]
        mwa, fifo, src = methods["moving_weighted_average"], methods["fifo"], methods["source_valuation"]
        assert mwa["quantity"] == fifo["quantity"]
        assert Decimal(mwa["quantity"]) == Decimal(src["quantity"])
        matches += body["reconciliation"]["status"] == "match"
        assert "moving_weighted_average" in body["rules"]
    # The rest are explained by 4-dp rounding of transfer costs in the source; reported, never hidden.
    assert matches >= 12


def test_cost_comparison_unknown_pair_is_404(client: TestClient) -> None:
    login(client, "alpha.admin")
    r = client.get("/api/analyses/cost-comparison", params={"item_id": "nope", "warehouse_id": "1100"})
    assert r.status_code == 404


def test_abc_requires_single_currency_and_compares_with_assigned(client: TestClient) -> None:
    login(client, "beta.admin")
    r = client.get("/api/analyses/abc", params={"a": "0.8", "b": "0.95"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "abc_mixed_currency"
    body = get(client, "/api/analyses/abc", a="0.8", b="0.95", currency="EUR")
    assert body["currency"] == "EUR"
    assert body["config"]["a_cutoff"] == "0.8"
    assert body["assigned_available"] is True
    assert sum(sum(row.values()) for row in body["matrix"].values()) == body["item_count"]
    values = [Decimal(i["value"]) for i in body["items"] if i["value"]]
    assert values == sorted(values, reverse=True)
    assert body["items"][0]["computed"] == "A"


def test_abc_rejects_bad_cutoffs(client: TestClient) -> None:
    login(client, "alpha.admin")
    assert client.get("/api/analyses/abc", params={"a": "0.95", "b": "0.8"}).status_code == 422
    assert client.get("/api/analyses/abc", params={"a": "0.8"}).status_code == 422
