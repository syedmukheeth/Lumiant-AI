"""Governed plans compile and pass the SQL guard on every planned source dialect, not only DuckDB (ISSUES #49, LA-09).

Compile-only: no database is contacted. The connectors for PostgreSQL, SQL Server and Oracle (V1) still need their
own conformance suite against real engines before they may be called supported (02-architecture/CONNECTORS.md).
"""

from __future__ import annotations

from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import mssql, mysql, oracle, postgresql, sqlite

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
# Time buckets render per dialect (compiler.DateBucket), so they are checked on every engine with a renderer,
# including the SQLite stand-in and MySQL.
ALL_DIALECTS: dict[str, tuple[sa.engine.Dialect, str]] = {
    **DIALECTS,
    "sqlite": (sqlite.dialect(), "sqlite"),
    "mysql": (mysql.dialect(), "mysql"),
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


_ISSUES = {"field": "txn_type", "op": "eq", "value": "ISSUE"}
BUCKET_PLANS: dict[str, dict[str, Any]] = {
    "month_sum": {
        "dataset": "inventory_transaction",
        "time_bucket": {"field": "posting_date", "grain": "month"},
        "measures": [{"field": "quantity", "agg": "sum", "alias": "issued"}],
        "filters": [_ISSUES],
    },
    "quarter_by_warehouse": {
        "dataset": "inventory_transaction",
        "time_bucket": {"field": "posting_date", "grain": "quarter"},
        "dimensions": ["warehouse_id"],
        "measures": [{"field": "quantity", "agg": "sum", "alias": "qty"}],
    },
    "day_desc_paged": {
        "dataset": "inventory_transaction",
        "time_bucket": {"field": "posting_date", "grain": "day"},
        "measures": [{"field": "txn_id", "agg": "count", "alias": "n"}],
        "order_by": [{"field": "period", "direction": "desc"}],
        "limit": 10,
        "offset": 10,
    },
    "year_value": {
        "dataset": "purchase_record",
        "time_bucket": {"field": "order_date", "grain": "year"},
        "measures": [{"field": "quantity", "agg": "sum", "alias": "ordered"}],
        "order_by": [{"field": "ordered", "direction": "desc"}],
    },
    "month_listing": {  # no measures: one period per row, no grouping
        "dataset": "inventory_transaction",
        "time_bucket": {"field": "posting_date", "grain": "month"},
        "dimensions": ["txn_id"],
        "limit": 5,
    },
}


@pytest.fixture(scope="module")
def alpha(registry: TenantRegistry) -> TenantMapping:
    return TenantMapping(registry.get("demo-alpha"))


@pytest.fixture(scope="module")
def delta(registry: TenantRegistry) -> TenantMapping:
    return TenantMapping(registry.get("demo-delta"))


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


# ------------------------------------------------------------------------------------------- time buckets
def render_for_guard(mapping: TenantMapping, principal: Principal, plan: dict[str, Any], dialect: str) -> str:
    """SQL as the guard sees it. MySQL drivers bind with %s, which sqlglot cannot parse (true of every plan on MySQL,
    not only buckets; ISSUES follow-up), so MySQL is checked with values inlined; its '%' doubling is kept."""
    if dialect != "mysql":
        return render(mapping, principal, plan, ALL_DIALECTS[dialect][0])
    vp = PlanValidator(mapping, mapping.tenant.policies).validate(QueryPlan.model_validate(plan), principal)
    stmt = compile_plan(vp, mapping, dialect="mysql")
    return str(stmt.compile(dialect=ALL_DIALECTS["mysql"][0], compile_kwargs={"literal_binds": True}))


@pytest.mark.parametrize("dialect", list(ALL_DIALECTS))
@pytest.mark.parametrize("plan", list(BUCKET_PLANS))
def test_bucket_plan_compiles_and_passes_the_guard(
    alpha: TenantMapping, principals: dict[str, Principal], dialect: str, plan: str
) -> None:
    for user in ("alpha.admin", "alpha.north_manager"):  # with and without the injected scope filter
        sql = render_for_guard(alpha, principals[user], BUCKET_PLANS[plan], dialect)
        check_sql(sql, ALL_DIALECTS[dialect][1], alpha.physical_tables())
        assert " AS period" in sql


@pytest.mark.parametrize("dialect", list(ALL_DIALECTS))
@pytest.mark.parametrize("grain", ["day", "month", "quarter", "year"])
def test_bucket_on_a_joined_date_field(
    delta: TenantMapping, principals: dict[str, Principal], dialect: str, grain: str
) -> None:
    plan = {
        "dataset": "purchase_record",
        "time_bucket": {"field": "supplier.certification_expiry", "grain": grain},
        "measures": [{"field": "po_id", "agg": "count_distinct", "alias": "orders"}],
    }
    for user in ("delta.admin", "delta.planner"):
        sql = render_for_guard(delta, principals[user], plan, dialect)
        check_sql(sql, ALL_DIALECTS[dialect][1], delta.physical_tables())
        assert "JOIN" in sql.upper()


# Expected period expression per dialect and grain (format strings inline, so SELECT and GROUP BY match exactly).
BUCKET_SQL = {
    ("duckdb", "month"): "strftime(b.\"BUDAT\", '%Y-%m')",
    ("sqlite", "month"): "strftime('%Y-%m', b.\"BUDAT\")",
    ("postgresql", "month"): "TO_CHAR(b.\"BUDAT\", 'YYYY-MM')",
    ("mysql", "month"): "DATE_FORMAT(b.`BUDAT`, '%%Y-%%m')",  # %-paramstyle driver: '%' doubled
    ("mssql", "month"): "CONVERT(char(7), b.[BUDAT], 126)",
    ("oracle", "month"): "TO_CHAR(b.\"BUDAT\", 'YYYY-MM')",
    ("duckdb", "day"): "strftime(b.\"BUDAT\", '%Y-%m-%d')",
    ("mssql", "year"): "CONVERT(char(4), b.[BUDAT], 126)",
    ("postgresql", "quarter"): 'TO_CHAR(b."BUDAT", \'YYYY-"Q"Q\')',
    ("duckdb", "quarter"): "strftime(b.\"BUDAT\", '%Y') || '-Q' || CAST(EXTRACT(quarter FROM b.\"BUDAT\") AS VARCHAR)",
    ("mssql", "quarter"): "CONVERT(char(4), b.[BUDAT], 126) + '-Q' + CAST(DATEPART(quarter, b.[BUDAT]) AS char(1))",
    ("mysql", "quarter"): "CONCAT(DATE_FORMAT(b.`BUDAT`, '%%Y'), '-Q', EXTRACT(QUARTER FROM b.`BUDAT`))",
}


@pytest.mark.parametrize(("dialect", "grain"), list(BUCKET_SQL))
def test_bucket_renders_the_dialect_format_in_select_group_and_order(
    alpha: TenantMapping, principals: dict[str, Principal], dialect: str, grain: str
) -> None:
    plan = {**BUCKET_PLANS["month_sum"], "time_bucket": {"field": "posting_date", "grain": grain}}
    sql = render(alpha, principals["alpha.admin"], plan, ALL_DIALECTS[dialect][0])
    expected = BUCKET_SQL[(dialect, grain)]
    assert sql.count(expected) >= 3, sql  # SELECT, GROUP BY, ORDER BY
