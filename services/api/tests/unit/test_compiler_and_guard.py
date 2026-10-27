"""Compiler output is parameterized; the SQL guard refuses anything but plain reads of mapped tables."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from lumiant.auth.principal import Principal
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.compiler import compile_plan, escape_like
from lumiant.query.plan import QueryPlan
from lumiant.query.sql_guard import SqlGuardError, check_sql
from lumiant.query.validator import PlanValidator
from lumiant.tenancy.registry import TenantRegistry

DIALECT = sa.create_engine("duckdb:///:memory:").dialect  # same paramstyle as the connector


@pytest.fixture(scope="module")
def alpha(registry: TenantRegistry) -> TenantMapping:
    return TenantMapping(registry.get("demo-alpha"))


def compiled(mapping: TenantMapping, principal: Principal, raw: dict[str, object]) -> tuple[str, dict[str, object]]:
    vp = PlanValidator(mapping, mapping.tenant.policies).validate(QueryPlan.model_validate(raw), principal)
    comp = compile_plan(vp, mapping).compile(dialect=DIALECT, compile_kwargs={"render_postcompile": True})
    return str(comp), dict(comp.params)


@pytest.mark.security
def test_values_are_bound_not_inlined(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    sql, params = compiled(
        alpha,
        principals["alpha.north_manager"],
        {
            "dataset": "stock_balance",
            "dimensions": ["item.item_group"],
            "measures": [{"field": "quantity", "agg": "sum", "alias": "qty"}],
            "filters": [{"field": "item.description", "op": "contains", "value": "'; DROP TABLE ZV_STOCK; --"}],
        },
    )
    assert "DROP TABLE" not in sql
    assert "1100" not in sql  # injected scope values are parameters too
    assert "%'!; DROP TABLE ZV!_STOCK; --%" not in sql
    assert any("DROP TABLE" in str(v) for v in params.values())
    assert '"ZV_STOCK"' in sql
    assert '"ZV_MATERIAL"' in sql
    assert "LEFT OUTER JOIN" in sql
    assert "ESCAPE '!'" in sql


def test_limit_fetches_one_extra_row(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    _, params = compiled(
        alpha, principals["alpha.admin"], {"dataset": "stock_balance", "dimensions": ["item_id"], "limit": 25}
    )
    assert 26 in params.values()


def test_escape_like() -> None:
    assert escape_like("50%_off!") == "50!%!_off!!"


def test_compiled_plan_passes_guard(alpha: TenantMapping, principals: dict[str, Principal]) -> None:
    sql, _ = compiled(
        alpha,
        principals["alpha.admin"],
        {
            "dataset": "stock_balance",
            "dimensions": ["warehouse.name"],
            "measures": [{"field": "stock_value", "agg": "sum"}],
        },
    )
    check_sql(sql, "duckdb", alpha.physical_tables())


@pytest.mark.security
@pytest.mark.parametrize(
    ("sql", "reason"),
    [
        ("SELECT 1; DROP TABLE ZV_STOCK", "multiple_statements"),
        ("DELETE FROM ZV_STOCK", "not_a_select"),
        ("INSERT INTO ZV_STOCK VALUES (1)", "not_a_select"),
        ("UPDATE ZV_STOCK SET LABST = 0", "not_a_select"),
        ("SELECT * FROM secrets", "table_not_allowed"),
        ("SELECT * FROM information_schema.tables", "system_object"),
        ("SELECT * FROM duckdb_settings()", "function_not_allowed"),
        ("SELECT * FROM read_csv('C:/secrets.csv')", "function_not_allowed"),
        ("SELECT getenv('HOME') FROM ZV_STOCK", "function_not_allowed"),
        ("SELECT MATNR FROM ZV_STOCK UNION SELECT name FROM other", "not_a_select"),
        ("SELECT * FROM other_schema.ZV_STOCK", "table_not_allowed"),
        ("SELECT * FROM _dataset_info", "table_not_allowed"),
    ],
)
def test_guard_rejects(alpha: TenantMapping, sql: str, reason: str) -> None:
    with pytest.raises(SqlGuardError) as exc:
        check_sql(sql, "duckdb", alpha.physical_tables())
    assert exc.value.reason.startswith(reason)
    assert exc.value.code == "query_rejected"


def test_guard_allows_ctes_over_mapped_tables(alpha: TenantMapping) -> None:
    check_sql(
        'WITH oh AS (SELECT MATNR, SUM(LABST) AS q FROM "ZV_STOCK" GROUP BY MATNR) '
        "SELECT r.MATNR, COALESCE(oh.q, 0) FROM ZV_REORDER r LEFT JOIN oh ON oh.MATNR = r.MATNR AND oh.q > 0 "
        "WHERE (r.MINBE IS NOT NULL OR r.MATNR ILIKE $1 ESCAPE '!') ORDER BY oh.q / NULLIF(r.MINBE, 0)",
        "duckdb",
        alpha.physical_tables(),
    )
