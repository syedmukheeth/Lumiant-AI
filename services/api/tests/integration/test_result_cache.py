"""S11 speed work: the hot paths share results through `lumiant.analyses.cache` without changing what anyone sees.

A repeat call within the cache window runs no source query, still writes an audit row (reason "cache"), returns a
copy, never crosses scope or permissions, and refuses a caller without the permission before the cache is read.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from benchmarks.overview_load import counted_queries
from fastapi.testclient import TestClient

from lumiant.analyses import cache
from lumiant.analyses.concentration import run_concentration
from lumiant.analyses.risks import run_abc
from lumiant.audit.store import AuditStore
from lumiant.auth.principal import Principal
from lumiant.core.config import Settings
from lumiant.core.errors import AppError, ForbiddenError
from lumiant.main import create_app
from lumiant.metrics.service import MetricsService
from lumiant.planning.service import PlanningService
from lumiant.query.service import QueryService
from tests.conftest import AS_OF
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


def _cache_rows(audit_store: AuditStore, tenant_id: str, action: str) -> int:
    return sum(1 for e in audit_store.recent(tenant_id, limit=200) if e.action == action and e.reason_code == "cache")


def test_master_data_reuses_the_planning_load_and_still_audits(
    query_service: QueryService, principals: dict[str, Principal], audit_store: AuditStore
) -> None:
    cache.clear(query_service)
    svc = PlanningService(query_service)
    p = principals["delta.admin"]
    with counted_queries() as first:
        cold = svc.duplicates(p)
    before = _cache_rows(audit_store, "demo-delta", "analysis:duplicates")
    with counted_queries() as again:
        warm = svc.duplicates(p)
    assert first.count > 0
    assert again.count == 0
    assert warm == cold
    assert _cache_rows(audit_store, "demo-delta", "analysis:duplicates") == before + 1
    assert audit_store.recent("demo-delta", limit=1)[0].action == "planning:duplicates"  # the capability row too


def test_one_planning_load_serves_the_other_planning_screens(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    cache.clear(query_service)
    svc = PlanningService(query_service)
    p = principals["delta.admin"]
    svc.fulfilment(p, today=AS_OF)
    with counted_queries() as rest:
        svc.material_plan(p, today=AS_OF)
        svc.commitments(p, today=AS_OF)
        svc.lifecycle(p, today=AS_OF)
    assert rest.count == 0


def test_planning_results_never_cross_scope_or_permissions(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    cache.clear(query_service)
    svc = PlanningService(query_service)
    admin = svc.fulfilment(principals["delta.admin"], today=AS_OF)  # warms the cache for the admin's scope
    planner = svc.fulfilment(principals["delta.planner"], today=AS_OF)
    with cache.fresh_results():
        direct = svc.fulfilment(principals["delta.planner"], today=AS_OF)
    assert planner == direct
    assert {ln["key"] for ln in planner["lines"]} < {ln["key"] for ln in admin["lines"]}


def test_a_shared_planning_load_is_a_copy(query_service: QueryService, principals: dict[str, Principal]) -> None:
    cache.clear(query_service)
    svc = PlanningService(query_service)
    p = principals["delta.admin"]
    first = svc._load(p, AS_OF)
    first.data.items.clear()
    first.issues.append(first.issues[0] if first.issues else None)  # type: ignore[arg-type]
    again = svc._load(p, AS_OF)
    assert again.data.items
    assert None not in again.issues


def test_metric_repeat_runs_no_query_and_keeps_one_warning(
    query_service: QueryService, principals: dict[str, Principal], audit_store: AuditStore
) -> None:
    cache.clear(query_service)
    svc = MetricsService(query_service)
    p = principals["alpha.admin"]
    _, first = svc.run("inventory_value_total", p)
    before = _cache_rows(audit_store, "demo-alpha", "analysis:metric:inventory_value_total")
    with counted_queries() as again:
        _, second = svc.run("inventory_value_total", p)
        _, third = svc.run("inventory_value_total", p)
    assert again.count == 0
    assert second.rows == first.rows
    # The gap warning is added after the shared result is copied, so it must not pile up on later callers.
    assert [w.code for w in third.warnings] == [w.code for w in first.warnings]
    assert _cache_rows(audit_store, "demo-alpha", "analysis:metric:inventory_value_total") == before + 2


def test_metric_denial_is_checked_before_the_cache(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    cache.clear(query_service)
    svc = MetricsService(query_service)
    svc.run("inventory_value_total", principals["alpha.admin"])
    with pytest.raises(ForbiddenError):
        svc.run("inventory_value_total", principals["alpha.analyst"])


def test_abc_and_concentration_are_shared_and_still_need_cost_access(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    cache.clear(query_service)
    admin = principals["alpha.admin"]
    cut = {"a_cutoff": Decimal("0.8"), "b_cutoff": Decimal("0.95"), "currency": None}
    abc = run_abc(query_service, admin, **cut)
    conc = run_concentration(query_service, admin)
    with counted_queries() as again:
        assert run_abc(query_service, admin, **cut) == abc
        assert run_concentration(query_service, admin) == conc
    assert again.count == 0
    with pytest.raises(ForbiddenError):
        run_abc(query_service, principals["alpha.analyst"], **cut)
    with pytest.raises(AppError):
        run_concentration(query_service, principals["alpha.analyst"])


def test_inventory_filters_repeat_runs_no_query(data_dir: Path, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="filters-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF).status_code == 200
        first = client.get("/api/inventory/filters")
        with counted_queries() as again:
            second = client.get("/api/inventory/filters")
    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    assert again.count == 0


def test_sqlite_audit_store_commits_in_wal_without_full_sync(audit_store: AuditStore) -> None:
    with audit_store.engine.connect() as con:
        assert con.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert con.exec_driver_sql("PRAGMA synchronous").scalar() == 1  # NORMAL
