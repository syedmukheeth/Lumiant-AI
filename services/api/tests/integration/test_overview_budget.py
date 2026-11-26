"""The Overview's repeated work stays down (V0): a cold page load runs at most a fixed number of source queries, and
shared results never cross warehouse scope or permissions (`lumiant.analyses.cache`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from benchmarks.overview_load import OVERVIEW, counted_queries
from fastapi.testclient import TestClient

from lumiant.analyses import cache
from lumiant.analyses.below_reorder import BelowReorderFilters, _run_below_reorder, run_below_reorder
from lumiant.auth.principal import Principal
from lumiant.core.config import Settings
from lumiant.main import create_app
from lumiant.query.service import QueryService
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}

# Measured after V0 on the test tenant (TEST_RUNS S10-27), with a little headroom. Before V0 the same page set ran
# 79 queries on full-size data. Raise this only with a reason recorded in TEST_RUNS.
OVERVIEW_QUERY_BUDGET = 45


def test_cold_overview_stays_within_its_query_budget(data_dir: Path, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="budget-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF).status_code == 200
        with counted_queries() as total:
            for url in OVERVIEW:
                assert client.get(url).status_code == 200, url
    assert total.count <= OVERVIEW_QUERY_BUDGET, f"cold Overview ran {total.count} source queries"


def test_shared_results_never_cross_scope_or_permissions(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    cache.clear(query_service)
    args = {"limit": 12, "offset": 0}
    admin = run_below_reorder(query_service, principals["alpha.admin"], BelowReorderFilters(), **args)
    north = run_below_reorder(query_service, principals["alpha.north_manager"], BelowReorderFilters(), **args)
    direct = _run_below_reorder(query_service, principals["alpha.north_manager"], BelowReorderFilters(), **args)
    assert north.summary == direct.summary
    assert north.page == direct.page
    assert (north.page or {})["total"] < (admin.page or {})["total"]
    keys = {cache.scope_key(principals[u]) for u in ("alpha.admin", "alpha.north_manager", "alpha.analyst")}
    assert len(keys) == 3, "different scope or permissions must never share an entry"


def test_a_shared_result_is_a_copy(query_service: QueryService, principals: dict[str, Principal]) -> None:
    cache.clear(query_service)
    first = run_below_reorder(query_service, principals["alpha.admin"], BelowReorderFilters(), limit=12, offset=0)
    first.rows.clear()
    (first.summary or {}).clear()
    again = run_below_reorder(query_service, principals["alpha.admin"], BelowReorderFilters(), limit=12, offset=0)
    assert again.rows
    assert again.summary


def test_fresh_results_bypass_the_cache(query_service: QueryService, principals: dict[str, Principal]) -> None:
    cache.clear(query_service)
    p = principals["alpha.admin"]
    run_below_reorder(query_service, p, BelowReorderFilters(), limit=12, offset=0)
    with counted_queries() as cached_run:
        run_below_reorder(query_service, p, BelowReorderFilters(), limit=12, offset=0)
    with cache.fresh_results(), counted_queries() as fresh_run:
        run_below_reorder(query_service, p, BelowReorderFilters(), limit=12, offset=0)
    assert cached_run.count == 0
    assert fresh_run.count > 0
