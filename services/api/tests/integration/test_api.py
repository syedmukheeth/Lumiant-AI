"""HTTP-level tests: authentication, authorization, tenant isolation, envelopes, safe errors."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient

from lumiant.auth.provider import COOKIE_NAME
from lumiant.core.config import AuthMode, Settings
from lumiant.main import create_app
from tests.helpers import raw_duckdb

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}
SECRET = "test-secret-" + "x" * 40


@pytest.fixture(scope="module")
def app_settings(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Settings:
    db = tmp_path_factory.mktemp("api-appdb") / "app.db"
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret=SECRET,
        data_dir=data_dir,
        app_db_url=f"sqlite:///{db.as_posix()}",
        log_level="WARNING",
    )


@pytest.fixture(scope="module")
def client(app_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(app_settings)) as c:
        yield c


def login(client: TestClient, username: str) -> TestClient:
    client.cookies.clear()
    r = client.post("/api/auth/dev-login", json={"username": username}, headers=CSRF)
    assert r.status_code == 200, r.text
    return client


def get(client: TestClient, url: str, **params: Any) -> Any:
    r = client.get(url, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------------------------------------- basics
def test_health_and_security_headers(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.json() == {"status": "ok"}
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in r.headers
    ready = client.get("/api/health/ready").json()
    assert ready == {"status": "ok", "sources_available": 2, "sources_total": 2}


def test_dev_users_listed_with_notice(client: TestClient) -> None:
    body = get(client, "/api/auth/dev-users")
    assert "not for production" in body["notice"]
    assert {u["username"] for u in body["users"]} >= {"alpha.admin", "beta.user"}


# --------------------------------------------------------------------------------------------- authn
@pytest.mark.security
def test_login_requires_csrf_header(client: TestClient) -> None:
    r = client.post("/api/auth/dev-login", json={"username": "alpha.admin"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "csrf_failed"


@pytest.mark.security
def test_unknown_user_cannot_log_in(client: TestClient) -> None:
    r = client.post("/api/auth/dev-login", json={"username": "mallory"}, headers=CSRF)
    assert r.status_code == 401


@pytest.mark.security
def test_session_cookie_flags(client: TestClient) -> None:
    client.cookies.clear()
    r = client.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF)
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


@pytest.mark.security
def test_unauthenticated_requests_rejected(client: TestClient) -> None:
    client.cookies.clear()
    for url in ("/api/auth/me", "/api/metrics", "/api/inventory/balances", "/api/analyses/below-reorder"):
        r = client.get(url)
        assert r.status_code == 401, url
        assert r.json()["error"]["code"] == "not_authenticated"


def _token(**overrides: Any) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": "alpha.admin",
        "tid": "demo-alpha",
        "iss": "lumiant-dev",
        "aud": "lumiant-api",
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    claims.update(overrides)
    secret = claims.pop("secret", SECRET)
    alg = claims.pop("alg", "HS256")
    return jwt.encode(claims, secret, algorithm=alg)


@pytest.mark.security
@pytest.mark.parametrize(
    "token",
    [
        _token(secret="wrong-secret-" + "y" * 40),
        _token(exp=datetime.now(UTC) - timedelta(minutes=1)),
        _token(tid="demo-beta"),  # alpha user claiming the beta tenant
        _token(sub="ghost.user"),
        _token(aud="someone-else"),
        jwt.encode({"sub": "alpha.admin", "tid": "demo-alpha"}, key=None, algorithm="none"),  # type: ignore[arg-type]
        "not-a-jwt",
    ],
)
def test_forged_or_expired_tokens_rejected(client: TestClient, token: str) -> None:
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()


def test_me_describes_principal(client: TestClient) -> None:
    me = get(login(client, "alpha.north_manager"), "/api/auth/me")
    assert me["tenant"]["id"] == "demo-alpha"
    assert me["scope"]["warehouses"] == ["1100", "1110", "1120"]
    assert me["scope"]["departments"] == ["NORTH"]
    assert me["sections"] == ["overview", "inventory", "risks", "costs", "assistant", "reports"]
    assert "cost:read" in me["permissions"]


def test_logout_clears_session(client: TestClient) -> None:
    login(client, "alpha.admin")
    assert client.post("/api/auth/logout", headers=CSRF).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


# --------------------------------------------------------------------------------------------- data
def test_meta_reports_synthetic_and_freshness(client: TestClient) -> None:
    meta = get(login(client, "alpha.admin"), "/api/meta/tenant")
    assert meta["synthetic"] is True
    assert meta["data_as_of"] is not None
    assert meta["stale"] is False


def test_value_by_warehouse_matches_raw_sql(client: TestClient, alpha_db: Path) -> None:
    body = get(login(client, "alpha.admin"), "/api/metrics/inventory_value_by_warehouse")
    con = raw_duckdb(alpha_db)
    expected = dict(con.execute("SELECT WERKS, SUM(LABST*VERPR) FROM ZV_STOCK GROUP BY WERKS").fetchall())
    missing = con.execute("SELECT count(*) FROM ZV_STOCK WHERE VERPR IS NULL AND LABST <> 0").fetchone()
    con.close()
    got = {r["warehouse_id"]: Decimal(r["value"]) for r in body["data"]}
    assert got == {k: v for k, v in expected.items() if v is not None}
    assert all(isinstance(r["value"], str) for r in body["data"])  # decimals travel as strings
    assert body["metric"]["status"] == "draft"
    assert body["provenance"]["metric"]["id"] == "inventory_value_by_warehouse"
    assert missing is not None
    if missing[0]:
        assert any(w["code"] == "missing_valuation_price" for w in body["warnings"])


def test_counts_match_raw_sql(client: TestClient, alpha_db: Path) -> None:
    login(client, "alpha.admin")
    con = raw_duckdb(alpha_db)
    items = con.execute("SELECT count(DISTINCT MATNR) FROM ZV_STOCK WHERE LABST > 0").fetchone()
    lines = con.execute("SELECT count(*) FROM ZV_STOCK WHERE LABST > 0").fetchone()
    con.close()
    assert items is not None
    assert lines is not None
    assert get(client, "/api/metrics/items_in_stock")["data"][0]["items"] == items[0]
    assert get(client, "/api/metrics/stock_lines")["data"][0]["lines"] == lines[0]


@pytest.mark.security
def test_no_cost_user_cannot_see_values(client: TestClient) -> None:
    login(client, "alpha.analyst")
    listed = {m["id"] for m in get(client, "/api/metrics")["metrics"]}
    assert listed == {"items_in_stock", "stock_lines"}
    r = client.get("/api/metrics/inventory_value_total")
    assert r.status_code == 403
    rows = get(client, "/api/inventory/balances", limit=200)
    assert rows["data"]
    assert all("valuation_price" not in r and "stock_value" not in r for r in rows["data"])
    assert {r["warehouse_id"] for r in rows["data"]} == {"3100"}
    sorted_by_value = get(client, "/api/inventory/balances", sort="value")
    assert all("stock_value" not in r for r in sorted_by_value["data"])


@pytest.mark.security
def test_out_of_scope_warehouse_filter_forbidden(client: TestClient) -> None:
    login(client, "alpha.north_manager")
    r = client.get("/api/inventory/balances", params={"warehouse": ["1100", "3100"]})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden_scope"
    r = client.get("/api/analyses/below-reorder", params={"warehouse": "2100"})
    assert r.status_code == 403


@pytest.mark.security
def test_tenant_isolation(client: TestClient) -> None:
    login(client, "beta.user")
    whs = get(client, "/api/inventory/filters")["warehouses"]
    assert [w["id"] for w in whs] == ["LDS1"]
    value = get(client, "/api/metrics/inventory_value_by_warehouse")
    assert {(r["warehouse_id"], r["currency"]) for r in value["data"]} == {("LDS1", "GBP")}
    assert value["provenance"]["tenant_id"] == "demo-beta"
    r = client.get("/api/inventory/balances", params={"warehouse": "1100"})
    assert r.status_code == 403  # an alpha warehouse id is simply out of scope for a beta user
    text = json.dumps(get(client, "/api/inventory/balances", limit=200))
    assert "ZV_STOCK" not in text
    assert '"1100"' not in text


def test_beta_admin_sees_two_currencies_never_summed(client: TestClient) -> None:
    body = get(login(client, "beta.admin"), "/api/metrics/inventory_value_total")
    assert {r["currency"] for r in body["data"]} == {"EUR", "GBP"}
    assert any(w["code"] == "auto_grouped" for w in body["warnings"])
    assert body["provenance"]["auto_grouped"] == ["currency"]


def test_inventory_listing_filters_search_and_paging(client: TestClient, alpha_db: Path) -> None:
    login(client, "alpha.admin")
    filters = get(client, "/api/inventory/filters")
    assert {"warehouses", "item_groups", "abc_classes", "stages"} <= set(filters)
    page = get(client, "/api/inventory/balances", item_group="MECH_SPARES", limit=10, sort="quantity", dir="desc")
    assert page["page"]["total"] >= len(page["data"])
    assert all(r["item.item_group"] == "MECH_SPARES" for r in page["data"])
    qtys = [Decimal(r["quantity"]) for r in page["data"]]
    assert qtys == sorted(qtys, reverse=True)
    con = raw_duckdb(alpha_db)
    code = con.execute("SELECT MATNR FROM ZV_STOCK ORDER BY MATNR LIMIT 1").fetchone()
    con.close()
    assert code is not None
    found = get(client, "/api/inventory/balances", q=code[0])
    assert any(r["item_id"] == code[0] for r in found["data"])


def test_below_reorder_matches_independent_sql(client: TestClient, alpha_db: Path) -> None:
    body = get(login(client, "alpha.admin"), "/api/analyses/below-reorder", limit=200)
    con = raw_duckdb(alpha_db)
    expected = con.execute(
        """
        WITH oh AS (SELECT s.MATNR, s.WERKS, SUM(s.LABST) q FROM ZV_STOCK s JOIN ZV_MATERIAL m USING (MATNR)
                    WHERE s.MEINS = m.MEINS GROUP BY ALL)
        SELECT r.MATNR, r.WERKS FROM ZV_REORDER r LEFT JOIN oh ON oh.MATNR = r.MATNR AND oh.WERKS = r.WERKS
        WHERE r.MINBE IS NOT NULL AND coalesce(oh.q, 0) < r.MINBE
        """
    ).fetchall()
    scenarios = json.loads(con.execute("SELECT value FROM _dataset_info WHERE key='scenarios'").fetchone()[0])  # type: ignore[index]
    con.close()
    got = {(r["item_id"], r["warehouse_id"]) for r in body["data"]}
    assert body["summary"]["flagged"] == len(expected)
    assert got == {tuple(x) for x in expected}
    zero = {tuple(x) for x in scenarios["zero_stock_with_policy"]}
    assert zero <= got
    assert all(Decimal(r["on_hand"]) < Decimal(r["reorder_level"]) for r in body["data"])
    assert body["provenance"]["rule"].startswith("Item–warehouse pairs")


def test_below_reorder_scoped_for_department_admin(client: TestClient) -> None:
    body = get(login(client, "alpha.north_manager"), "/api/analyses/below-reorder", limit=200)
    assert {r["warehouse_id"] for r in body["data"]} <= {"1100", "1110", "1120"}
    assert body["provenance"]["filters"]["injected"][0]["value"] == ["1100", "1110", "1120"]


# --------------------------------------------------------------------------------------------- /api/query
def test_query_endpoint_requires_csrf_and_permission(client: TestClient) -> None:
    plan = {
        "dataset": "stock_balance",
        "dimensions": ["warehouse_id"],
        "measures": [{"field": "quantity", "agg": "sum"}],
    }
    login(client, "alpha.admin")
    assert client.post("/api/query", json=plan).status_code == 403
    r = client.post("/api/query", json=plan, headers=CSRF)
    assert r.status_code == 200
    assert {c["name"] for c in r.json()["columns"]} == {"warehouse_id", "uom", "sum_quantity"}
    login(client, "alpha.analyst")
    assert client.post("/api/query", json=plan, headers=CSRF).status_code == 403


@pytest.mark.security
def test_malformed_plans_give_safe_errors(client: TestClient) -> None:
    login(client, "alpha.admin")
    r = client.post(
        "/api/query", json={"dataset": "stock_balance", "dimensions": ["item_id"], "sql": "DROP TABLE x"}, headers=CSRF
    )
    assert r.status_code == 422
    assert "DROP TABLE" not in r.text
    r = client.post("/api/query", json={"dataset": "pg_catalog", "dimensions": ["x"]}, headers=CSRF)
    assert r.status_code == 400
    body = r.json()["error"]
    assert body["code"] == "dataset_not_available"
    assert body["request_id"]
    for leak in ("ZV_", "duckdb", "SELECT", "Traceback", str(Path.cwd())):
        assert leak not in r.text


def test_unknown_metric_is_404(client: TestClient) -> None:
    login(client, "alpha.admin")
    assert client.get("/api/metrics/does_not_exist").status_code == 404


@pytest.mark.security
def test_oidc_mode_refuses_to_start(app_settings: Settings) -> None:
    settings = app_settings.model_copy(update={"auth_mode": AuthMode.OIDC})
    with pytest.raises(RuntimeError, match="needs at least one tenant"):
        create_app(Settings.model_validate(settings.model_dump()))
