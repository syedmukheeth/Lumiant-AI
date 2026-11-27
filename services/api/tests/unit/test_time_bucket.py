"""Time buckets (`QueryPlan.time_bucket`): validation, ordering, output columns, guard allowlist and cache keys.

Per-dialect rendering and guard checks on all six engines are in test_dialect_matrix.py; results against a Python
reference are in tests/integration/test_time_buckets.py.
"""

from __future__ import annotations

from typing import Any

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from lumiant.auth.principal import Principal
from lumiant.canonical.catalog import FieldType
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.compiler import DateBucket
from lumiant.query.plan import Grain, QueryPlan
from lumiant.query.sql_guard import SqlGuardError, check_sql
from lumiant.query.validator import PlanRejectedError, PlanValidator, TimeBucketSpec
from lumiant.tenancy.registry import TenantRegistry


@pytest.fixture(scope="module")
def alpha(registry: TenantRegistry) -> TenantMapping:
    return TenantMapping(registry.get("demo-alpha"))


@pytest.fixture(scope="module")
def validator(alpha: TenantMapping) -> PlanValidator:
    return PlanValidator(alpha, alpha.tenant.policies)


def plan(**kwargs: Any) -> QueryPlan:
    return QueryPlan.model_validate(
        {
            "dataset": "inventory_transaction",
            "time_bucket": {"field": "posting_date", "grain": "month"},
            "measures": [{"field": "quantity", "agg": "sum", "alias": "qty"}],
            **kwargs,
        }
    )


def test_bucket_columns_come_first_and_are_text(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(plan(dimensions=["warehouse_id"]), principals["alpha.admin"])
    assert isinstance(vp.time_bucket, TimeBucketSpec)
    assert [c.name for c in vp.columns] == ["period", "warehouse_id", "uom", "qty"]
    assert vp.columns[0].type is FieldType.STRING
    assert vp.columns[0].kind == "dimension"
    assert vp.auto_grouped == ("uom",)  # quantities still never add across units
    assert "posting_date" in [r.ref for r in vp.referenced_fields()]  # provenance and audit name the date field


def test_default_order_is_oldest_period_first(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(plan(dimensions=["warehouse_id"]), principals["alpha.admin"])
    assert [(o.name, o.descending) for o in vp.order_by] == [("period", False), ("warehouse_id", False), ("uom", False)]


def test_order_by_period_or_measure(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    newest = validator.validate(plan(order_by=[{"field": "period", "direction": "desc"}]), principals["alpha.admin"])
    assert [(o.name, o.descending) for o in newest.order_by] == [("period", True), ("uom", False)]
    biggest = validator.validate(plan(order_by=[{"field": "qty", "direction": "desc"}]), principals["alpha.admin"])
    assert [(o.name, o.descending) for o in biggest.order_by] == [("qty", True), ("period", False), ("uom", False)]


def test_scope_injection_is_unchanged(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(plan(), principals["alpha.north_manager"])
    scope = [f for f in vp.filters if getattr(f, "origin", None) == "scope"]
    assert len(scope) == 1
    assert scope[0].field.ref == "warehouse_id"


def test_bucket_needs_a_date_field(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    with pytest.raises(PlanRejectedError) as exc:
        validator.validate(plan(time_bucket={"field": "quantity", "grain": "month"}), principals["alpha.admin"])
    assert exc.value.code == "invalid_time_bucket"
    with pytest.raises(PlanRejectedError) as exc:
        validator.validate(plan(time_bucket={"field": "item.description", "grain": "year"}), principals["alpha.admin"])
    assert exc.value.code == "invalid_time_bucket"


def test_bucket_field_must_exist_and_joins_must_be_approved(
    validator: PlanValidator, principals: dict[str, Principal]
) -> None:
    with pytest.raises(PlanRejectedError) as exc:
        validator.validate(plan(time_bucket={"field": "shipped_on", "grain": "day"}), principals["alpha.admin"])
    assert exc.value.code == "field_not_available"
    with pytest.raises(PlanRejectedError) as exc:
        validator.validate(plan(time_bucket={"field": "supplier.created", "grain": "day"}), principals["alpha.admin"])
    assert exc.value.code == "join_not_allowed"


def test_plan_shape_rules() -> None:
    with pytest.raises(ValidationError):
        plan(time_bucket={"field": "posting_date", "grain": "week"})
    with pytest.raises(ValidationError):
        plan(measures=[{"field": "quantity", "agg": "sum", "alias": "period"}])
    with pytest.raises(ValidationError):  # one bucket per plan
        plan(time_bucket=[{"field": "posting_date", "grain": "month"}, {"field": "posting_date", "grain": "year"}])
    with pytest.raises(ValidationError):
        plan(time_bucket={"field": "posting_date", "grain": "month", "format": "%Y"})
    assert (
        QueryPlan.model_validate(
            {"dataset": "inventory_transaction", "time_bucket": {"field": "posting_date", "grain": "year"}}
        ).time_bucket
        is not None
    )


# ------------------------------------------------------------------------------------------- compiler and guard
def test_grain_is_part_of_the_cache_key() -> None:
    t = sa.table("t", sa.column("d", sa.Date()))
    keys = {sa.select(DateBucket(t.c.d, g))._generate_cache_key().key for g in Grain}
    assert len(keys) == len(Grain)  # a month statement never reuses a year statement's compiled SQL


def test_unknown_dialects_refuse_to_guess_a_date_format() -> None:
    t = sa.table("t", sa.column("d", sa.Date()))
    with pytest.raises(sa.exc.CompileError):
        str(sa.select(DateBucket(t.c.d, Grain.MONTH)))


@pytest.mark.parametrize(
    ("sql", "dialect", "reason"),
    [
        ("SELECT CONCAT_WS('-', b.MBLNR, b.BUDAT) FROM ZV_MOVEMENT AS b", "mysql", "function_not_allowed"),
        ("SELECT TS_OR_DS_TO_TIMESTAMP(b.BUDAT) FROM ZV_MOVEMENT AS b", "duckdb", "function_not_allowed"),
        ("SELECT strftime(read_csv('x.csv'), '%Y') FROM ZV_MOVEMENT AS b", "duckdb", "function_not_allowed"),
        ("SELECT DATE_FORMAT(b.BUDAT, '%Y') FROM information_schema.tables AS b", "mysql", "system_object"),
    ],
)
def test_guard_allows_only_the_bucket_functions(alpha: TenantMapping, sql: str, dialect: str, reason: str) -> None:
    with pytest.raises(SqlGuardError) as exc:
        check_sql(sql, dialect, alpha.physical_tables())
    assert exc.value.reason.startswith(reason)
