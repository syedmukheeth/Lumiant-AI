"""Connector conformance (V1, 02-architecture/CONNECTORS.md): the same tenant mapping, pointed at a copy of the synthetic
warehouse in another SQL engine, gives the same figures as DuckDB, stays read-only, times out, and fails safely.

SQLite runs everywhere (development stand-in; it stores decimals as REAL, so its money is compared to 4 dp).
PostgreSQL runs when LUMIANT_TEST_PG_ADMIN_URL is set (CI job `api-postgres-redis`) and must match exactly.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from lumiant.analyses import cache
from lumiant.analyses.below_reorder import BelowReorderFilters, run_below_reorder
from lumiant.analyses.risks import run_abc, run_data_quality, run_dormant, run_expiring
from lumiant.audit.store import AuditStore
from lumiant.auth.principal import Principal, principal_for_dev_user
from lumiant.connectors.base import ConnectorError
from lumiant.connectors.probe import probe
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.connectors.sql_connector import SqlConnector
from lumiant.core.config import Settings
from lumiant.core.errors import AppError
from lumiant.main import create_app
from lumiant.metrics.service import MetricsService
from lumiant.query.service import QueryService
from lumiant.synthetic.copy import copy_duckdb
from lumiant.tenancy.models import ConnectionConfig
from lumiant.tenancy.registry import TenantRegistry
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
ENV = "LUMIANT_TEST_SOURCE_URL"
CSRF = {"X-Requested-With": "lumiant"}
PG_ADMIN = os.environ.get("LUMIANT_TEST_PG_ADMIN_URL")


def _postgres_copy(alpha_db: Path) -> Iterator[str]:
    assert PG_ADMIN
    name = f"lumiant_src_{uuid.uuid4().hex[:12]}"
    admin = sa.create_engine(PG_ADMIN, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    url = sa.make_url(PG_ADMIN).set(database=name).render_as_string(hide_password=False)
    copy_duckdb(alpha_db, url)
    try:
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(
    scope="module",
    params=[
        "sqlite",
        pytest.param("postgresql", marks=pytest.mark.skipif(not PG_ADMIN, reason="needs LUMIANT_TEST_PG_ADMIN_URL")),
    ],
)
def source_url(
    request: pytest.FixtureRequest, alpha_db: Path, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[str]:
    if request.param == "sqlite":
        target = tmp_path_factory.mktemp("sqlsrc") / "alpha.sqlite"
        copy_duckdb(alpha_db, f"sqlite:///{target.as_posix()}")
        yield f"sqlite:///{target.as_posix()}"
    else:
        yield from _postgres_copy(alpha_db)


@pytest.fixture(scope="module")
def sql_service(
    source_url: str, registry: TenantRegistry, data_dir: Path, audit_store: AuditStore
) -> Iterator[QueryService]:
    alpha = registry.get("demo-alpha")
    cfg = alpha.model_copy(update={"connection": ConnectionConfig(type="sql", secret_ref=f"env:{ENV}")})
    os.environ[ENV] = source_url
    tenants = TenantRegistry({"demo-alpha": cfg})
    connectors = ConnectorRegistry(tenants, data_dir)
    yield QueryService(tenants, connectors, audit_store)
    connectors.dispose_all()
    os.environ.pop(ENV, None)


@pytest.fixture(scope="module")
def admin(registry: TenantRegistry) -> Principal:
    tenant = registry.get("demo-alpha")
    return principal_for_dev_user(tenant, next(u for u in tenant.dev_users if u.username == "alpha.admin"))


def _exact(source_url: str) -> bool:
    return not source_url.startswith("sqlite")


def same(a: Any, b: Any, exact: bool) -> bool:
    """Equal figures; SQLite (REAL storage) is compared to 4 decimal places."""
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], exact) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y, exact) for x, y in zip(a, b, strict=True))
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        da, db = Decimal(str(a)), Decimal(str(b))
        return da == db if exact else da.quantize(Decimal("0.0001")) == db.quantize(Decimal("0.0001"))
    return bool(a == b)


@pytest.mark.parametrize(
    "metric", ["inventory_value_total", "inventory_value_by_warehouse", "items_in_stock", "stock_lines"]
)
def test_metrics_match_duckdb(
    sql_service: QueryService, query_service: QueryService, admin: Principal, source_url: str, metric: str
) -> None:
    _, on_sql = MetricsService(sql_service).run(metric, admin)
    _, on_duck = MetricsService(query_service).run(metric, admin)
    assert on_sql.rows, metric
    assert same(on_sql.rows, on_duck.rows, _exact(source_url))


def test_analyses_match_duckdb(
    sql_service: QueryService,
    query_service: QueryService,
    admin: Principal,
    principals: dict[str, Principal],
    source_url: str,
) -> None:
    exact = _exact(source_url)
    for svc in (sql_service, query_service):
        cache.clear(svc)
    below = [
        run_below_reorder(s, admin, BelowReorderFilters(), limit=12, offset=0) for s in (sql_service, query_service)
    ]
    assert below[0].summary == below[1].summary
    assert below[0].page == below[1].page
    exp = [run_expiring(s, admin, days=60, limit=5) for s in (sql_service, query_service)]
    assert exp[0].summary == exp[1].summary
    dormant = [run_dormant(s, admin, days=180, limit=5, offset=0) for s in (sql_service, query_service)]
    assert dormant[0].page == dormant[1].page
    abc = [
        run_abc(s, admin, a_cutoff=Decimal("0.8"), b_cutoff=Decimal("0.95"), currency=None)
        for s in (sql_service, query_service)
    ]
    assert abc[0]["matrix"] == abc[1]["matrix"]
    assert same([i["value"] for i in abc[0]["items"]], [i["value"] for i in abc[1]["items"]], exact)
    dq = [{c["id"]: c["count"] for c in run_data_quality(s, admin)["checks"]} for s in (sql_service, query_service)]
    assert dq[0] == dq[1]
    scoped = run_below_reorder(
        sql_service, principals["alpha.north_manager"], BelowReorderFilters(), limit=12, offset=0
    )
    assert (scoped.page or {})["total"] < (below[0].page or {})["total"], "warehouse scope applies on the SQL source"


def test_the_source_refuses_writes(source_url: str) -> None:
    connector = SqlConnector(source_url)

    def write() -> None:
        with connector._engine.connect() as conn:
            conn.execute(sa.text('DELETE FROM "ZV_STOCK"'))
            conn.commit()

    try:
        with pytest.raises(sa.exc.DBAPIError):
            write()
    finally:
        connector.dispose()


def test_a_long_query_is_cancelled(source_url: str) -> None:
    connector = SqlConnector(source_url)
    mv = sa.table("ZV_MOVEMENT", sa.column("MATNR"))
    a, b, c = mv.alias("a"), mv.alias("b"), mv.alias("c")
    heavy = sa.select(sa.func.count()).select_from(a.join(b, sa.true()).join(c, sa.true()))
    try:
        with pytest.raises(ConnectorError) as exc:
            connector.execute(heavy, fetch_limit=1, timeout_s=0.3)
        assert exc.value.code == "query_timeout"
    finally:
        connector.dispose()


def test_an_unconfigured_source_fails_safely(
    registry: TenantRegistry, data_dir: Path, audit_store: AuditStore, admin: Principal
) -> None:
    alpha = registry.get("demo-alpha")
    cfg = alpha.model_copy(update={"connection": ConnectionConfig(type="sql", secret_ref="env:LUMIANT_TEST_NOT_SET")})
    os.environ.pop("LUMIANT_TEST_NOT_SET", None)
    tenants = TenantRegistry({"demo-alpha": cfg})
    svc = QueryService(tenants, ConnectorRegistry(tenants, data_dir), audit_store)
    with pytest.raises(AppError) as exc:
        MetricsService(svc).run("items_in_stock", admin)
    assert exc.value.code == "source_unavailable"


def test_only_known_engines_are_accepted() -> None:
    with pytest.raises(ConnectorError) as exc:
        SqlConnector("firebird://user:pw@host/db")
    assert exc.value.code == "unsupported_source"


def test_sql_connections_need_a_secret_reference() -> None:
    with pytest.raises(ValueError, match="secret_ref"):
        ConnectionConfig(type="sql")
    with pytest.raises(ValueError, match="secret_ref"):
        ConnectionConfig(type="sql", secret_ref="env:X_URL", path="data/x.duckdb")


# ------------------------------------------------------------------------------------------- Connect: test a URL
def test_probe_proves_read_only_and_lists_tables(source_url: str) -> None:
    result = probe(source_url, allow_sqlite=True)
    assert result["ok"] is True
    assert {"ZV_STOCK", "ZV_MATERIAL"} <= {o["name"] for o in result["objects"]}
    if source_url.startswith("sqlite"):
        assert result["read_only"]["status"] == "proved"
    assert "sqlite:" not in str(result), "the URL is never echoed"
    assert "postgresql" not in str(result.get("objects"))


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("not a url at all", "invalid_url"),
        ("firebird://u:p@h/db", "unsupported_source"),
        ("sqlite:///whatever.db", "unsupported_source"),  # SQLite only outside production, see below
    ],
)
def test_probe_refuses_safely(url: str, code: str) -> None:
    result = probe(url, allow_sqlite=False)
    assert result == {"ok": False, "code": code, "message": result["message"]}
    assert "u:p" not in result["message"]


def test_probe_reports_an_unreachable_database(tmp_path: Path) -> None:
    result = probe(f"sqlite:///{(tmp_path / 'missing.sqlite').as_posix()}", allow_sqlite=True)
    assert result["ok"] is False
    assert result["code"] == "source_unavailable"


def test_source_endpoints_are_admin_only(data_dir: Path, tmp_path: Path, source_url: str) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="source-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        client.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF)
        status = client.get("/api/admin/source").json()
        assert status["healthy"] is True
        assert status["engine"] == "duckdb"
        assert {d["dataset"]: d["rows"] for d in status["datasets"]}["stock_balance"] > 0
        assert client.post("/api/admin/source/test", json={"url": source_url}).status_code == 403  # CSRF header
        tested = client.post("/api/admin/source/test", json={"url": source_url}, headers=CSRF).json()
        assert tested["ok"] is True
        client.cookies.clear()
        client.post("/api/auth/dev-login", json={"username": "alpha.analyst"}, headers=CSRF)
        assert client.get("/api/admin/source").status_code == 403
        assert client.post("/api/admin/source/test", json={"url": source_url}, headers=CSRF).status_code == 403
