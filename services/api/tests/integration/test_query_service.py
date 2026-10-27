"""QueryService against the generated synthetic warehouses, checked with independent raw SQL."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pytest
import sqlalchemy as sa

from lumiant.audit.store import AuditEvent, AuditStore
from lumiant.auth.principal import Principal
from lumiant.connectors.base import ConnectorError
from lumiant.connectors.duckdb_connector import DuckDBConnector
from lumiant.core.errors import AppError
from lumiant.query.plan import QueryPlan
from lumiant.query.service import QueryService
from lumiant.query.sql_guard import SqlGuardError
from tests.helpers import raw_duckdb

pytestmark = pytest.mark.integration


@pytest.fixture
def raw_alpha(alpha_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    con = raw_duckdb(alpha_db)
    yield con
    con.close()


@pytest.fixture
def raw_beta(beta_db: Path) -> Iterator[duckdb.DuckDBPyConnection]:
    con = raw_duckdb(beta_db)
    yield con
    con.close()


def value_by_warehouse(svc: QueryService, who: Principal) -> dict[tuple[str, str], Decimal]:
    result = svc.run_plan(
        QueryPlan(
            dataset="stock_balance",
            dimensions=["warehouse_id"],
            measures=[{"field": "stock_value", "agg": "sum", "alias": "value"}],  # type: ignore[list-item]
        ),
        who,
        action="test",
    )
    return {(r["warehouse_id"], r["currency"]): r["value"] for r in result.rows}


def test_alpha_value_matches_independent_sql(
    query_service: QueryService, principals: dict[str, Principal], raw_alpha: duckdb.DuckDBPyConnection
) -> None:
    expected = {
        (w, c): v
        for w, c, v in raw_alpha.execute(
            "SELECT WERKS, WAERS, SUM(LABST * VERPR) FROM ZV_STOCK GROUP BY ALL"
        ).fetchall()
    }
    assert value_by_warehouse(query_service, principals["alpha.admin"]) == expected


def test_beta_value_matches_independent_sql_per_currency(
    query_service: QueryService, principals: dict[str, Principal], raw_beta: duckdb.DuckDBPyConnection
) -> None:
    expected = {
        (w, c): v
        for w, c, v in raw_beta.execute(
            "SELECT warehouse_code, currency_code, SUM(qty_on_hand * unit_value) FROM inv.stock_on_hand GROUP BY ALL"
        ).fetchall()
    }
    got = value_by_warehouse(query_service, principals["beta.admin"])
    assert got == expected
    assert {c for _, c in got} == {"EUR", "GBP"}


@pytest.mark.security
def test_scoped_user_only_sees_scope(query_service: QueryService, principals: dict[str, Principal]) -> None:
    got = query_service.run_plan(
        QueryPlan(
            dataset="stock_balance",
            dimensions=["warehouse_id"],
            measures=[{"field": "item_id", "agg": "count"}],
        ),  # type: ignore[list-item]
        principals["alpha.north_manager"],
        action="test",
    )
    assert {r["warehouse_id"] for r in got.rows} <= {"1100", "1110", "1120"}
    assert got.provenance["filters"]["injected"][0]["value"] == ["1100", "1110", "1120"]


@pytest.mark.security
def test_beta_user_cannot_reach_other_tenant_or_warehouse(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    got = query_service.run_plan(
        QueryPlan(dataset="warehouse", dimensions=["warehouse_id", "name"]),
        principals["beta.user"],
        action="test",
    )
    assert [r["warehouse_id"] for r in got.rows] == ["LDS1"]
    with pytest.raises(AppError) as exc:
        query_service.run_plan(
            QueryPlan.model_validate(
                {
                    "dataset": "stock_balance",
                    "dimensions": ["item_id"],
                    "filters": [{"field": "warehouse_id", "op": "eq", "value": "1100"}],
                }
            ),
            principals["beta.user"],
            action="test",
        )
    assert exc.value.code == "forbidden_scope"


def test_listing_truncation_and_total(query_service: QueryService, principals: dict[str, Principal]) -> None:
    got = query_service.run_plan(
        QueryPlan(dataset="stock_balance", dimensions=["item_id", "warehouse_id", "lot_id", "quantity"], limit=5),
        principals["alpha.admin"],
        action="test",
        with_total=True,
    )
    assert len(got.rows) == 5
    assert got.truncated
    assert got.page is not None
    assert got.page["total"] > 5
    assert any(w.code == "truncated" for w in got.warnings)
    assert "uom" in got.rows[0]  # unit companion added automatically


@pytest.mark.security
def test_injection_strings_are_data(query_service: QueryService, principals: dict[str, Principal]) -> None:
    for payload in ["' OR 1=1 --", "%", "_", "'); DROP TABLE ZV_STOCK; --"]:
        got = query_service.run_plan(
            QueryPlan.model_validate(
                {
                    "dataset": "item",
                    "dimensions": ["item_id"],
                    "filters": [{"field": "description", "op": "contains", "value": payload}],
                }
            ),
            principals["alpha.admin"],
            action="test",
        )
        assert got.rows == []


def test_prompt_injection_text_is_returned_as_plain_data(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    got = query_service.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "item",
                "dimensions": ["item_id", "description"],
                "filters": [{"field": "description", "op": "contains", "value": "ignore all previous instructions"}],
            }
        ),
        principals["alpha.admin"],
        action="test",
    )
    assert len(got.rows) == 1


def test_provenance_contents(query_service: QueryService, principals: dict[str, Principal]) -> None:
    admin = query_service.run_plan(
        QueryPlan(dataset="stock_balance", measures=[{"field": "stock_value", "agg": "sum"}]),  # type: ignore[list-item]
        principals["alpha.admin"],
        action="test",
    )
    prov = admin.provenance
    assert prov["synthetic"] is True
    assert prov["source_objects"] == ["ZV_STOCK"]
    assert prov["fields"]["stock_value"] == "ZV_STOCK.LABST * ZV_STOCK.VERPR"
    assert prov["data_as_of"] is not None
    assert "sql" in prov  # super_admin has query:view_sql
    manager = query_service.run_plan(
        QueryPlan(dataset="stock_balance", measures=[{"field": "stock_value", "agg": "sum"}]),  # type: ignore[list-item]
        principals["alpha.north_manager"],
        action="test",
    )
    assert "sql" not in manager.provenance


@pytest.mark.security
def test_denials_are_audited_without_values(
    query_service: QueryService, principals: dict[str, Principal], audit_store: AuditStore
) -> None:
    with pytest.raises(AppError):
        query_service.run_plan(
            QueryPlan.model_validate(
                {
                    "dataset": "stock_balance",
                    "dimensions": ["item_id"],
                    "filters": [{"field": "warehouse_id", "op": "eq", "value": "SECRET-VALUE-3100"}],
                }
            ),
            principals["alpha.analyst"],
            action="audit-test",
        )
    with sa.orm.Session(audit_store.engine) as s:
        event = s.scalars(sa.select(AuditEvent).where(AuditEvent.action == "audit-test")).one()
        assert event.decision == "deny"
        assert event.reason_code == "forbidden_scope"
        assert event.user_id == "alpha.analyst"
        dumped = " ".join(str(v) for v in vars(event).values())
        assert "SECRET-VALUE" not in dumped


@pytest.mark.security
def test_sql_guard_blocks_unmapped_tables_in_execute_select(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    info = sa.table("_dataset_info", sa.column("key"), sa.column("value"))
    with pytest.raises(SqlGuardError):
        query_service.execute_select(
            principals["alpha.admin"], sa.select(info.c.value), action="test", dataset="x", fetch_limit=1
        )


@pytest.mark.security
def test_database_level_read_only(alpha_db: Path) -> None:
    connector = DuckDBConnector(alpha_db)
    stock = sa.table("ZV_STOCK", sa.column("MATNR"))
    with pytest.raises(ConnectorError):
        connector.execute(sa.insert(stock).values(MATNR="X"), fetch_limit=1, timeout_s=5)  # type: ignore[arg-type]
    connector.dispose()


def test_timeout_interrupts_long_queries(alpha_db: Path) -> None:
    connector = DuckDBConnector(alpha_db)
    big: Any = sa.func.range(100_000_000).table_valued("range").alias("a")
    other: Any = sa.func.range(100_000).table_valued("range").alias("b")
    stmt = sa.select(sa.func.sum(big.c.range * other.c.range)).select_from(big.join(other, sa.true()))
    with pytest.raises(ConnectorError) as exc:
        connector.execute(stmt, fetch_limit=1, timeout_s=0.2)
    assert exc.value.code == "query_timeout"
    assert connector.health()
    connector.dispose()


def test_missing_source_is_reported_safely(tmp_path: Path) -> None:
    connector = DuckDBConnector(tmp_path / "absent.duckdb")
    assert not connector.health()
    with pytest.raises(ConnectorError) as exc:
        connector.execute(sa.select(sa.literal(1)), fetch_limit=1, timeout_s=1)
    assert exc.value.code == "source_unavailable"
