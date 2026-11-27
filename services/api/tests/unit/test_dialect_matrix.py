"""Governed plans compile and pass the SQL guard on every planned source dialect, not only DuckDB (ISSUES #49, LA-09).

Compile-only: no database is contacted. The connectors for PostgreSQL, SQL Server and Oracle (V1) still need their
own conformance suite against real engines before they may be called supported (02-architecture/CONNECTORS.md).
"""

from __future__ import annotations

from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mssql, oracle, postgresql

from lumiant.auth.principal import Principal
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.compiler import compile_plan
from lumiant.query.plan import QueryPlan
from lumiant.query.sql_guard import check_sql
from lumiant.query.validator import PlanRejectedError, PlanValidator
from lumiant.tenancy.registry import TenantRegistry


def _mssql() -> sa.engine.Dialect:
    d = mssql.dialect()
    d.server_version_info = (16, 0)  # SQL Server 2022: OFFSET / FETCH available
    d._supports_offset_fetch = True  # set by SQLAlchemy on connect; no connection here
    return d


# SQLAlchemy dialect, sqlglot dialect for the guard
DIALECTS: dict[str, tuple[sa.engine.Dialect, str]] = {
    "duckdb": (sa.create_engine("duckdb:///:memory:").dialect, "duckdb"),
    "postgresql": (postgresql.dialect(), "postgres"),
    "mssql": (_mssql(), "tsql"),
    "oracle": (oracle.dialect(), "oracle"),
}

PLANS: dict[str, dict[str, Any]] = {
    "count_only": {"dataset": "stock_balance", "measures": [{"field": "item_id", "agg": "count", "alias": "n"}]},
    "grouped": {
        "dataset": "stock_balance",
        "dimensions": ["warehouse_id"],
        "measures": [{"field": "quantity", "agg": "sum", "alias": "qty"}],
    },
    "contains": {
        "dataset": "stock_balance",
        "dimensions": ["item_id", "item.description"],
        "filters": [{"field": "item.description", "op": "contains", "value": "pump"}],
    },
    "paged": {"dataset": "item", "dimensions": ["item_id", "item_code"], "limit": 10, "offset": 20},
    "ordered_desc": {
        "dataset": "stock_balance",
        "dimensions": ["item_id"],
        "measures": [{"field": "stock_value", "agg": "sum", "alias": "value"}],
        "order_by": [{"field": "value", "direction": "desc"}],
        "limit": 5,
    },
}


@pytest.fixture(scope="module")
def alpha(registry: TenantRegistry) -> TenantMapping:
    return TenantMapping(registry.get("demo-alpha"))


def render(mapping: TenantMapping, principal: Principal, plan: dict[str, Any], dialect: sa.engine.Dialect) -> str:
    vp = PlanValidator(mapping, mapping.tenant.policies).validate(QueryPlan.model_validate(plan), principal)
    stmt = compile_plan(vp, mapping, dialect=dialect.name)
    return str(stmt.compile(dialect=dialect, compile_kwargs={"render_postcompile": True}))


@pytest.mark.parametrize("dialect", list(DIALECTS))
@pytest.mark.parametrize("plan", list(PLANS))
def test_plan_compiles_and_passes_the_guard(
    alpha: TenantMapping, principals: dict[str, Principal], dialect: str, plan: str
) -> None:
    sa_dialect, guard_dialect = DIALECTS[dialect]
    for user in ("alpha.admin", "alpha.north_manager"):  # with and without the injected scope filter
        sql = render(alpha, principals[user], PLANS[plan], sa_dialect)
        check_sql(sql, guard_dialect, alpha.physical_tables())


def test_sql_server_gets_no_nulls_last(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    sql = render(alpha, principals["alpha.admin"], PLANS["ordered_desc"], DIALECTS["mssql"][0])
    assert "NULLS LAST" not in sql.upper()
    assert "CASE WHEN" in sql.upper()  # nulls sorted last through a flag instead


def test_single_number_plans_use_top_on_sql_server(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    sql = render(alpha, principals["alpha.admin"], PLANS["count_only"], DIALECTS["mssql"][0]).upper()
    assert "TOP" in sql
    assert "OFFSET" not in sql


def test_paged_plans_keep_an_order_on_sql_server(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    sql = render(alpha, principals["alpha.admin"], PLANS["paged"], DIALECTS["mssql"][0]).upper()
    assert "ORDER BY" in sql
    assert "OFFSET" in sql


def test_other_dialects_still_sort_nulls_last(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    for name in ("duckdb", "postgresql", "oracle"):
        sql = render(alpha, principals["alpha.admin"], PLANS["ordered_desc"], DIALECTS[name][0]).upper()
        assert "NULLS LAST" in sql, name


def test_paging_without_an_order_is_refused(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    with pytest.raises(PlanRejectedError) as exc:
        render(alpha, principals["alpha.admin"], {**PLANS["count_only"], "offset": 10}, DIALECTS["mssql"][0])
    assert exc.value.code == "invalid_offset"
