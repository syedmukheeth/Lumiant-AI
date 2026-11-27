"""Time buckets run end to end: monthly (and day / quarter / year) ISSUE quantities from the governed engine equal a
Python reference computed from the raw movements, on DuckDB and on the SQLite stand-in, with and without warehouse
scope. Also the Analyst's `query_inventory` `period` argument and its chart block (contract with the web ChartBlock).
"""

from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from lumiant.agent.data_tools import QueryArgs, catalog_note, to_plan
from lumiant.agent.tools import TOOLS, ToolContext
from lumiant.audit.store import AuditStore
from lumiant.auth.principal import Principal
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.plan import QueryPlan
from lumiant.query.service import QueryService
from lumiant.query.validator import PlanRejectedError
from lumiant.synthetic.copy import copy_duckdb
from lumiant.tenancy.models import ConnectionConfig
from lumiant.tenancy.registry import TenantRegistry
from tests.helpers import raw_duckdb

pytestmark = pytest.mark.integration
ENV = "LUMIANT_TEST_BUCKET_SOURCE_URL"
GRAINS = ["day", "month", "quarter", "year"]


@pytest.fixture(scope="module")
def sqlite_service(
    alpha_db: Path, registry: TenantRegistry, data_dir: Path, audit_store: AuditStore, tmp_path_factory: Any
) -> Iterator[QueryService]:
    target = tmp_path_factory.mktemp("bucketsrc") / "alpha.sqlite"
    copy_duckdb(alpha_db, f"sqlite:///{target.as_posix()}")
    cfg = registry.get("demo-alpha").model_copy(
        update={"connection": ConnectionConfig(type="sql", secret_ref=f"env:{ENV}")}
    )
    os.environ[ENV] = f"sqlite:///{target.as_posix()}"
    tenants = TenantRegistry({"demo-alpha": cfg})
    connectors = ConnectorRegistry(tenants, data_dir)
    yield QueryService(tenants, connectors, audit_store)
    connectors.dispose_all()
    os.environ.pop(ENV, None)


@pytest.fixture(scope="module")
def services(query_service: QueryService, sqlite_service: QueryService) -> dict[str, QueryService]:
    return {"duckdb": query_service, "sqlite": sqlite_service}


def _period(d: date, grain: str) -> str:
    match grain:
        case "day":
            return d.isoformat()
        case "month":
            return f"{d.year:04d}-{d.month:02d}"
        case "quarter":
            return f"{d.year:04d}-Q{(d.month - 1) // 3 + 1}"
    return f"{d.year:04d}"


def reference(alpha_db: Path, registry: TenantRegistry, grain: str, scope: set[str] | None) -> dict[tuple, Decimal]:
    """Sum of ISSUE quantity per (period, uom), from the raw source rows with the tenant's own mapping."""
    mapping = TenantMapping(registry.get("demo-alpha"))
    ds = "inventory_transaction"
    cols = [mapping.physical_column(ds, f) for f in ("txn_type", "posting_date", "quantity", "uom", "warehouse_id")]
    codes = mapping.value_maps().get(ds, {}).get("txn_type", {})
    sql = f"SELECT {', '.join(f'"{c}"' for c in cols)} FROM {mapping.source_object(ds)}"
    conn = raw_duckdb(alpha_db)
    try:
        rows = conn.execute(sql).fetchall()
    finally:
        conn.close()
    sums: dict[tuple, Decimal] = defaultdict(Decimal)
    for txn_type, posted, qty, uom, warehouse in rows:
        if codes.get(txn_type, txn_type) != "ISSUE" or (scope is not None and warehouse not in scope):
            continue
        key = (_period(posted, grain) if posted is not None else None, uom)
        sums[key] += Decimal(str(qty))
    return dict(sums)


def issued_plan(grain: str) -> QueryPlan:
    return QueryPlan.model_validate(
        {
            "dataset": "inventory_transaction",
            "time_bucket": {"field": "posting_date", "grain": grain},
            "measures": [{"field": "quantity", "agg": "sum", "alias": "issued"}],
            "filters": [{"field": "txn_type", "op": "eq", "value": "ISSUE"}],
            "limit": 1000,
        }
    )


@pytest.mark.parametrize("engine", ["duckdb", "sqlite"])
@pytest.mark.parametrize("grain", GRAINS)
@pytest.mark.parametrize("user", ["alpha.admin", "alpha.north_manager"])
def test_bucketed_issue_quantities_match_the_raw_movements(
    services: dict[str, QueryService],
    principals: dict[str, Principal],
    alpha_db: Path,
    registry: TenantRegistry,
    engine: str,
    grain: str,
    user: str,
) -> None:
    principal = principals[user]
    res = services[engine].run_plan(issued_plan(grain), principal, action="test:bucket")
    assert not res.truncated
    assert [c.name for c in res.columns] == ["period", "uom", "issued"]
    got = {(r["period"], r["uom"]): Decimal(str(r["issued"])) for r in res.rows}
    scope = None if principal.scope.all else set(principal.scope.ids)
    expected = reference(alpha_db, registry, grain, scope)
    assert expected, "the synthetic data should have issues"
    assert got.keys() == expected.keys()
    for key, value in expected.items():
        if engine == "duckdb":
            assert got[key] == value, key
        else:  # SQLite stores decimals as REAL: compared to 4 dp, as in the connector conformance suite
            assert got[key].quantize(Decimal("0.0001")) == value.quantize(Decimal("0.0001")), key
    periods = [r["period"] for r in res.rows]
    assert periods == sorted(periods)  # oldest first by default
    assert res.provenance["fields"]["posting_date"].endswith("BUDAT")


def test_month_buckets_have_iso_labels(query_service: QueryService, principals: dict[str, Principal]) -> None:
    by_grain = {
        g: {r["period"] for r in query_service.run_plan(issued_plan(g), principals["alpha.admin"], action="t").rows}
        for g in GRAINS
    }
    assert all(len(p) == 10 and p[4] == "-" and p[7] == "-" for p in by_grain["day"])
    assert all(len(p) == 7 and p[4] == "-" for p in by_grain["month"])
    assert all(len(p) == 7 and p[4:6] == "-Q" and p[6] in "1234" for p in by_grain["quarter"])
    assert all(len(p) == 4 and p.isdigit() for p in by_grain["year"])
    assert len(by_grain["month"]) >= 12  # 12 months of synthetic history


# ------------------------------------------------------------------------------------------- query_inventory
MONTHLY_ISSUES = {
    "dataset": "inventory_transaction",
    "period": {"field": "posting_date", "grain": "month"},
    "measures": [{"field": "quantity", "agg": "sum", "alias": "issued"}],
    "filters": [{"field": "txn_type", "op": "eq", "value": "ISSUE"}],
    "limit": 100,
}


def test_period_maps_to_the_time_bucket() -> None:
    plan = to_plan(QueryArgs.model_validate(MONTHLY_ISSUES))
    assert plan.time_bucket is not None
    assert (plan.time_bucket.field, plan.time_bucket.grain.value) == ("posting_date", "month")
    assert to_plan(QueryArgs.model_validate({**MONTHLY_ISSUES, "period": None})).time_bucket is None


@pytest.mark.parametrize("engine", ["duckdb", "sqlite"])
def test_query_inventory_period_adds_a_line_chart(
    services: dict[str, QueryService], principals: dict[str, Principal], engine: str
) -> None:
    out = TOOLS["query_inventory"].run(
        ToolContext(services[engine], principals["alpha.admin"]), QueryArgs.model_validate(MONTHLY_ISSUES)
    )
    assert out.ok
    assert [b["type"] for b in out.blocks] == ["table", "chart"]  # chart after the table, no bar block
    table, chart = out.blocks
    assert [c["key"] for c in table["columns"]] == ["period", "uom", "issued"]
    assert chart == {
        "type": "chart",
        "variant": "line",
        "title": "Issued by month",
        "x_key": "period",
        "series": [{"key": "issued", "label": "Issued", "kind": "qty", "unit_key": "uom"}],
        "rows": chart["rows"],
    }
    assert len(chart["rows"]) == len(table["rows"])
    for crow, trow in zip(chart["rows"], table["rows"], strict=True):
        assert crow.keys() == trow.keys()
        assert all(isinstance(v, str) for v in crow.values())  # values as strings, also from SQLite REAL
        assert Decimal(crow["issued"]) == Decimal(str(trow["issued"]))
        assert crow["period"] == trow["period"]


def test_query_inventory_charts_only_the_money_or_quantity_measure(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    args = {**MONTHLY_ISSUES, "measures": [*MONTHLY_ISSUES["measures"], {"field": "txn_id", "agg": "count"}]}
    out = TOOLS["query_inventory"].run(ToolContext(query_service, principals["alpha.admin"]), QueryArgs(**args))
    chart = next(b for b in out.blocks if b["type"] == "chart")
    assert [s["key"] for s in chart["series"]] == ["issued"]
    assert all(isinstance(r["count_txn_id"], str) for r in chart["rows"])


def test_query_inventory_period_with_another_grouping_has_no_chart(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    args = QueryArgs.model_validate({**MONTHLY_ISSUES, "group_by": ["warehouse_id"]})
    out = TOOLS["query_inventory"].run(ToolContext(query_service, principals["alpha.admin"]), args)
    assert out.ok
    assert [b["type"] for b in out.blocks] == ["table"]  # several rows per period: neither line nor bars


def test_query_inventory_keeps_bars_for_non_period_groupings(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    args = QueryArgs.model_validate({**MONTHLY_ISSUES, "period": None, "group_by": ["warehouse_id"]})
    out = TOOLS["query_inventory"].run(ToolContext(query_service, principals["alpha.admin"]), args)
    assert [b["type"] for b in out.blocks] == ["bar", "table"]


def test_query_inventory_refuses_a_period_on_a_non_date_field(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    args = QueryArgs.model_validate({**MONTHLY_ISSUES, "period": {"field": "quantity", "grain": "month"}})
    with pytest.raises(PlanRejectedError) as exc:  # the agent loop turns this into a failed tool result
        TOOLS["query_inventory"].run(ToolContext(query_service, principals["alpha.admin"]), args)
    assert exc.value.code == "invalid_time_bucket"


def test_catalog_note_lists_the_period_fields(query_service: QueryService, principals: dict[str, Principal]) -> None:
    note = catalog_note(ToolContext(query_service, principals["alpha.admin"]))
    movements = next(line for line in note.splitlines() if line.startswith("- inventory_transaction:"))
    assert "Period fields: posting_date." in movements
    purchases = next(line for line in note.splitlines() if line.startswith("- purchase_record:"))
    assert "Period fields: order_date, receipt_date." in purchases
    assert "grain: day|month|quarter|year" in note
