"""Onboarding/administration: schema drift detection, capability matrix, reconciliation gate, audit explorer."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from lumiant.admin.service import capability_matrix, discover, type_category
from lumiant.connectors.duckdb_connector import DuckDBConnector
from lumiant.core.config import BASE_DIR, Settings
from lumiant.main import create_app
from lumiant.mapping.resolver import TenantMapping
from lumiant.tenancy.models import TenantConfig
from lumiant.tenancy.registry import TenantRegistry

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


@pytest.fixture(scope="module")
def client(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="admin-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=f"sqlite:///{(tmp_path_factory.mktemp('admdb') / 'app.db').as_posix()}",
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client: TestClient, user: str) -> TestClient:
    client.cookies.clear()
    assert client.post("/api/auth/dev-login", json={"username": user}, headers=CSRF).status_code == 200
    return client


def tenant_variant(name: str, mutate: Any) -> TenantMapping:
    raw = yaml.safe_load((BASE_DIR / "config" / "tenants" / f"{name}.yaml").read_text(encoding="utf-8"))
    mutate(raw)
    return TenantMapping(TenantConfig.model_validate(raw))


def test_type_categories() -> None:
    assert type_category("DECIMAL(18,4)") == "number"
    assert type_category("VARCHAR") == "text"
    assert type_category("TIMESTAMP") == "date"
    assert type_category("BOOLEAN") == "boolean"


@pytest.mark.parametrize(("tenant", "db"), [("demo-alpha", "alpha_db"), ("demo-beta", "beta_db")])
def test_discovery_finds_no_drift_on_generated_warehouses(
    tenant: str, db: str, registry: TenantRegistry, request: pytest.FixtureRequest
) -> None:
    connector = DuckDBConnector(request.getfixturevalue(db))
    result = discover(TenantMapping(registry.get(tenant)), connector)
    connector.dispose()
    assert result["verdict"] == "ok", [d for d in result["datasets"] if d["problems"]]
    assert result["healthy"] is True
    assert all(d["status"] == "ok" for d in result["datasets"])


def test_discovery_reports_drift_and_unmapped_columns(alpha_db: Path) -> None:
    def mutate(raw: dict[str, Any]) -> None:
        raw["datasets"]["stock_balance"]["fields"]["quantity"] = "LABST_RENAMED"  # column no longer exists
        raw["datasets"]["item"]["fields"]["shelf_life_days"] = "MAKTX"  # text column mapped as integer
        raw["datasets"]["supplier"]["source"] = "ZV_GONE"  # table removed
        del raw["datasets"]["warehouse"]["fields"]["site"]  # physical column becomes unmapped

    connector = DuckDBConnector(alpha_db)
    result = discover(tenant_variant("demo-alpha", mutate), connector)
    connector.dispose()
    by = {d["dataset"]: d for d in result["datasets"]}
    assert result["verdict"] == "drift"
    assert by["stock_balance"]["problems"][0] == {
        "kind": "missing_column",
        "field": "quantity",
        "column": "LABST_RENAMED",
    }
    assert any(p["kind"] == "type_mismatch" and p["field"] == "shelf_life_days" for p in by["item"]["problems"])
    assert by["supplier"]["status"] == "missing_table"
    assert "ORT01" in [u["column"] for u in by["warehouse"]["unmapped"]]
    assert result["totals"]["missing_tables"] == 1


def test_capability_matrix_explains_gaps() -> None:
    full = {c["id"]: c for c in capability_matrix(tenant_variant("demo-alpha", lambda r: None))}
    assert all(c["available"] for c in full.values())

    def drop(raw: dict[str, Any]) -> None:
        del raw["datasets"]["lot"]["fields"]["receipt_date"]
        del raw["datasets"]["reorder_policy"]

    partial = {c["id"]: c for c in capability_matrix(tenant_variant("demo-alpha", drop))}
    assert partial["fifo_pick"]["available"] is False
    assert "lot.receipt_date" in partial["fifo_pick"]["missing"]
    assert partial["below_reorder"]["available"] is False
    assert partial["below_reorder"]["explanation"].startswith("Not available:")
    assert partial["inventory_value"]["available"] is True


@pytest.mark.security
def test_admin_endpoints_require_admin(client: TestClient) -> None:
    one_row = {"rows": [{"warehouse_id": "1100", "currency": "USD", "value": "1"}]}
    for user in ("alpha.analyst", "alpha.north_manager"):
        login(client, user)
        for url in ("/api/admin/schema", "/api/admin/capabilities", "/api/admin/audit"):
            assert client.get(url).status_code == 403, (user, url)
        assert client.post("/api/admin/reconciliation", json=one_row, headers=CSRF).status_code == 403
    client.cookies.clear()
    assert client.get("/api/admin/schema").status_code == 401


def test_schema_and_capabilities_endpoints(client: TestClient) -> None:
    login(client, "alpha.admin")
    assert client.get("/api/admin/schema").json()["verdict"] == "ok"
    caps = client.get("/api/admin/capabilities").json()["capabilities"]
    assert {c["id"] for c in caps} >= {"below_reorder", "cost_comparison", "fifo_pick"}
    assert "admin" in client.get("/api/auth/me").json()["sections"]


def test_reconciliation_gate(client: TestClient) -> None:
    login(client, "alpha.admin")
    report = client.get("/api/reports/value_by_warehouse").json()
    truth = [
        {"warehouse_id": r["warehouse_id"], "currency": r["currency"], "value": r["value"]} for r in report["rows"]
    ]
    ok = client.post("/api/admin/reconciliation", json={"tolerance": "0.01", "rows": truth}, headers=CSRF).json()
    assert ok["passed"] is True
    assert ok["counts"] == {"match": len(truth)}

    off = [dict(r) for r in truth]
    off[0]["value"] = str(Decimal(off[0]["value"]) + Decimal("5.00"))
    off.append({"warehouse_id": "9999", "currency": "USD", "value": "1"})
    bad = client.post("/api/admin/reconciliation", json={"tolerance": "0.01", "rows": off}, headers=CSRF).json()
    assert bad["passed"] is False
    lines = {ln["warehouse_id"]: ln for ln in bad["lines"]}
    assert lines[off[0]["warehouse_id"]]["status"] == "variance"
    assert Decimal(lines[off[0]["warehouse_id"]]["difference"]) == Decimal("-5.00")
    assert lines["9999"]["status"] == "missing_in_platform"

    partial = client.post("/api/admin/reconciliation", json={"rows": truth[:1]}, headers=CSRF).json()
    assert partial["passed"] is False
    assert "missing_in_customer_report" in partial["counts"]
    not_a_number = {"rows": [{"warehouse_id": "1", "currency": "USD", "value": "abc"}]}
    assert client.post("/api/admin/reconciliation", json=not_a_number, headers=CSRF).status_code == 422
    assert client.post("/api/admin/reconciliation", json={"rows": []}, headers=CSRF).status_code == 422


@pytest.mark.security
def test_reconciliation_compares_currencies_separately(client: TestClient) -> None:
    login(client, "beta.admin")
    report = client.get("/api/reports/value_by_warehouse").json()
    rows = [
        {
            "warehouse_id": r["warehouse_id"],
            "currency": "USD" if r["currency"] == "EUR" else r["currency"],
            "value": r["value"],
        }
        for r in report["rows"]
    ]
    result = client.post("/api/admin/reconciliation", json={"rows": rows}, headers=CSRF).json()
    assert result["passed"] is False  # a EUR figure reported as USD must not match


def test_audit_explorer_is_tenant_scoped_and_value_free(client: TestClient) -> None:
    login(client, "alpha.admin")
    client.get("/api/metrics/inventory_value_total")
    events = client.get("/api/admin/audit", params={"limit": 20}).json()["events"]
    assert events
    assert set(events[0]) >= {"occurred_at", "action", "decision", "rows", "duration_ms"}
    denied = client.get("/api/admin/audit", params={"decision": "deny"}).json()["events"]
    assert all(e["decision"] == "deny" for e in denied)
    metric = client.get("/api/admin/audit", params={"action": "metric:"}).json()["events"]
    assert metric
    assert all(e["action"].startswith("metric:") for e in metric)
    assert client.get("/api/admin/audit", params={"action": "x'; DROP"}).status_code == 422
    login(client, "beta.admin")
    other = client.get("/api/admin/audit", params={"limit": 200}).json()["events"]
    assert all(not e["user_id"].startswith("alpha.") for e in other)
