"""Analyses keep working past row caps (V0, docs/05-plan/PRODUCT_V3_PLAN.md §6): results are computed in the source
or paged, never refused or silently cut because a company has more than a fixed number of items or movements."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumiant.analyses.risks import run_abc, run_cost_comparison, run_data_quality
from lumiant.api.inventory import filters
from lumiant.audit.store import AuditStore
from lumiant.auth.principal import Principal, principal_for_dev_user
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.costing.abc import AbcConfig, classify
from lumiant.query.service import QueryService
from lumiant.tenancy.registry import TenantRegistry
from tests.helpers import raw_duckdb

pytestmark = pytest.mark.integration
A, B = Decimal("0.8"), Decimal("0.95")


def independent_abc(alpha_db: Path) -> tuple[dict[str, Decimal], dict[str, str | None], dict[str, str | None]]:
    """Per-item on-hand value and the assigned class from raw SQL, classified by the reference Python rule."""
    con = raw_duckdb(alpha_db)
    rows = con.execute(
        "SELECT MATNR, sum(LABST * VERPR) FROM ZV_STOCK WHERE LABST > 0 GROUP BY MATNR HAVING sum(LABST * VERPR) IS NOT NULL"
    ).fetchall()
    assigned = {
        str(m): (str(c) if c else None) for m, c in con.execute("SELECT MATNR, ABCKZ FROM ZV_MATERIAL").fetchall()
    }
    con.close()
    values = {str(m): Decimal(v) for m, v in rows}
    return values, classify(values, AbcConfig(A, B)), assigned


def test_abc_in_the_source_matches_the_reference_rule(
    query_service: QueryService, principals: dict[str, Principal], alpha_db: Path
) -> None:
    result = run_abc(query_service, principals["alpha.admin"], a_cutoff=A, b_cutoff=B, currency=None)
    values, computed, assigned = independent_abc(alpha_db)

    matrix: dict[str, dict[str, int]] = {}
    for item_id, cls in computed.items():
        a = assigned.get(item_id) or "none"
        matrix.setdefault(cls or "none", {}).setdefault(a, 0)
        matrix[cls or "none"][a] += 1
    assert result["matrix"] == matrix
    assert result["item_count"] == len(values)
    assert result["differences"] == sum(
        1 for i, c in computed.items() if assigned.get(i) is not None and assigned.get(i) != c
    )
    ranked = sorted(values, key=lambda i: (-values[i], i))
    listed = result["items"]
    assert [i["item_id"] for i in listed] == ranked[: len(listed)]
    assert all(i["computed"] == computed[i["item_id"]] for i in listed)
    assert all(Decimal(i["value"]) == values[i["item_id"]].quantize(Decimal("0.01")) for i in listed)


@pytest.fixture
def tight_rows(registry: TenantRegistry, data_dir: Path, audit_store: AuditStore) -> Iterator[QueryService]:
    """demo-alpha with a row cap far below its item count (the old ABC refused anything above its cap)."""
    alpha = registry.get("demo-alpha")
    tight = alpha.model_copy(
        update={"policies": alpha.policies.model_copy(update={"max_rows": 20, "default_rows": 20})}
    )
    connectors = ConnectorRegistry(TenantRegistry({"demo-alpha": tight}), data_dir)
    yield QueryService(TenantRegistry({"demo-alpha": tight}), connectors, audit_store)
    connectors.dispose_all()


def test_abc_is_not_limited_by_the_row_cap(tight_rows: QueryService, registry: TenantRegistry, alpha_db: Path) -> None:
    tenant = registry.get("demo-alpha")
    admin = principal_for_dev_user(tenant, next(u for u in tenant.dev_users if u.username == "alpha.admin"))
    result = run_abc(tight_rows, admin, a_cutoff=A, b_cutoff=B, currency=None)
    values, _, _ = independent_abc(alpha_db)
    assert len(values) > 20
    assert result["item_count"] == len(values)


def test_abc_respects_warehouse_scope(query_service: QueryService, principals: dict[str, Principal]) -> None:
    everyone = run_abc(query_service, principals["alpha.admin"], a_cutoff=A, b_cutoff=B, currency=None)
    north = run_abc(query_service, principals["alpha.north_manager"], a_cutoff=A, b_cutoff=B, currency=None)
    assert 0 < north["item_count"] <= everyone["item_count"]
    assert north["provenance"]["filters"]["injected"], "the scope filter must be recorded as injected"
    assert not everyone["provenance"]["filters"]["injected"]


def _busiest_pair(alpha_db: Path) -> tuple[str, str, int]:
    con = raw_duckdb(alpha_db)
    row = con.execute(
        "SELECT MATNR, WERKS, count(*) AS n FROM ZV_MOVEMENT GROUP BY MATNR, WERKS ORDER BY n DESC, MATNR, WERKS LIMIT 1"
    ).fetchone()
    con.close()
    assert row is not None
    return str(row[0]), str(row[1]), int(row[2])


def test_cost_comparison_reads_every_movement_in_pages(
    tight_rows: QueryService,
    query_service: QueryService,
    registry: TenantRegistry,
    principals: dict[str, Principal],
    alpha_db: Path,
) -> None:
    item, warehouse, n = _busiest_pair(alpha_db)
    assert n > 20, "the busiest pair must hold more movements than the tight row cap"
    tenant = registry.get("demo-alpha")
    admin = principal_for_dev_user(tenant, next(u for u in tenant.dev_users if u.username == "alpha.admin"))
    paged = run_cost_comparison(tight_rows, admin, item_id=item, warehouse_id=warehouse)
    whole = run_cost_comparison(query_service, principals["alpha.admin"], item_id=item, warehouse_id=warehouse)
    assert paged["movements_used"] == whole["movements_used"] == n
    assert paged["methods"] == whole["methods"]


def test_item_code_check_covers_every_item(tight_rows: QueryService, registry: TenantRegistry, alpha_db: Path) -> None:
    tenant = registry.get("demo-alpha")
    admin = principal_for_dev_user(tenant, next(u for u in tenant.dev_users if u.username == "alpha.admin"))
    checks = {c["id"]: c for c in run_data_quality(tight_rows, admin)["checks"]}
    con = raw_duckdb(alpha_db)
    row = con.execute("SELECT count(*) FROM ZV_MATERIAL").fetchone()
    con.close()
    assert row is not None
    assert checks["invalid_item_codes"]["checked"] == row[0] > 20
    assert checks["invalid_item_codes"]["partial"] is False


@pytest.fixture
def tiny_rows(registry: TenantRegistry, data_dir: Path, audit_store: AuditStore) -> Iterator[QueryService]:
    alpha = registry.get("demo-alpha")
    tiny = alpha.model_copy(update={"policies": alpha.policies.model_copy(update={"max_rows": 2, "default_rows": 2})})
    connectors = ConnectorRegistry(TenantRegistry({"demo-alpha": tiny}), data_dir)
    yield QueryService(TenantRegistry({"demo-alpha": tiny}), connectors, audit_store)
    connectors.dispose_all()


def test_filter_lists_say_when_they_are_cut(
    tiny_rows: QueryService, query_service: QueryService, registry: TenantRegistry, principals: dict[str, Principal]
) -> None:
    whole = filters(principals["alpha.admin"], SimpleNamespace(query=query_service))  # type: ignore[arg-type]
    assert whole["truncated"] == []
    assert whole["item_groups"] == sorted(whole["item_groups"])
    assert [w["id"] for w in whole["warehouses"]] == sorted(w["id"] for w in whole["warehouses"])

    tenant = registry.get("demo-alpha")
    admin = principal_for_dev_user(tenant, next(u for u in tenant.dev_users if u.username == "alpha.admin"))
    cut = filters(admin, SimpleNamespace(query=tiny_rows))  # type: ignore[arg-type]
    assert {"warehouses", "item_groups"} <= set(cut["truncated"])
    assert cut["limit"] == 2
    assert cut["item_groups"] == whole["item_groups"][:2]
