"""Plan validation rules (docs/02-architecture/QUERY_ENGINE.md §2)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from lumiant.auth.principal import Principal
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.plan import Op, QueryPlan
from lumiant.query.validator import FilterGroup, PlanRejectedError, PlanValidator, ValidatedPlan
from lumiant.tenancy.registry import TenantRegistry


@pytest.fixture(scope="module")
def validator(registry: TenantRegistry) -> PlanValidator:
    cfg = registry.get("demo-alpha")
    return PlanValidator(TenantMapping(cfg), cfg.policies)


def plan(**kwargs: Any) -> QueryPlan:
    return QueryPlan.model_validate({"dataset": "stock_balance", **kwargs})


def rejected(validator: PlanValidator, p: QueryPlan, who: Principal) -> PlanRejectedError:
    with pytest.raises(PlanRejectedError) as exc:
        validator.validate(p, who)
    return exc.value


def test_valid_aggregate_plan(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(
        plan(dimensions=["warehouse_id"], measures=[{"field": "stock_value", "agg": "sum", "alias": "value"}]),
        principals["alpha.admin"],
    )
    assert isinstance(vp, ValidatedPlan)
    assert [c.name for c in vp.columns] == ["warehouse_id", "currency", "value"]
    assert vp.auto_grouped == ("currency",)
    assert vp.limit == 100


def test_quantity_sum_is_grouped_by_uom(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(plan(measures=[{"field": "quantity", "agg": "sum"}]), principals["alpha.admin"])
    assert vp.auto_grouped == ("uom",)


def test_listing_cost_field_brings_currency(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(plan(dimensions=["item_id", "valuation_price"]), principals["alpha.admin"])
    assert "currency" in [d.ref for d in vp.dimensions]


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"dataset": "ghost", "dimensions": ["item_id"]}, "dataset_not_available"),
        ({"dimensions": ["nonexistent"]}, "field_not_available"),
        ({"dimensions": ["supplier.name"]}, "join_not_allowed"),
        ({"dimensions": ["item.ghost"]}, "field_not_available"),
        (
            {"dimensions": ["quantity"], "measures": [{"field": "stock_value", "agg": "sum"}]},
            "invalid_dimension",
        ),
        ({"measures": [{"field": "uom", "agg": "sum"}]}, "invalid_aggregation"),
        ({"measures": [{"field": "valuation_price", "agg": "sum"}]}, "invalid_aggregation"),
        (
            {"dimensions": ["item_id"], "filters": [{"field": "quantity", "op": "contains", "value": "1"}]},
            "invalid_filter",
        ),
        (
            {"dimensions": ["item_id"], "filters": [{"field": "quantity", "op": "gt", "value": "abc"}]},
            "invalid_value",
        ),
        (
            {"dimensions": ["item_id"], "filters": [{"field": "quantity", "op": "gt", "value": "NaN"}]},
            "invalid_value",
        ),
        (
            {"dimensions": ["item_id"], "filters": [{"field": "uom", "op": "in", "value": []}]},
            "invalid_filter",
        ),
        (
            {"dimensions": ["item_id"], "filters": [{"field": "uom", "op": "is_null", "value": "x"}]},
            "invalid_filter",
        ),
        ({"dimensions": ["item_id"], "order_by": [{"field": "uom"}]}, "invalid_order"),
        ({"dimensions": ["item_id"], "limit": 5000}, "limit_exceeded"),
        (
            {
                "dimensions": ["warehouse_id"],
                "measures": [{"field": "quantity", "agg": "sum", "alias": "q"}],
                "having": [{"measure": "nope", "op": "gt", "value": "1"}],
            },
            "invalid_having",
        ),
    ],
)
def test_rejections(
    validator: PlanValidator, principals: dict[str, Principal], kwargs: dict[str, Any], code: str
) -> None:
    assert rejected(validator, plan(**kwargs), principals["alpha.admin"]).code == code


def test_unknown_keys_and_floats_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        QueryPlan.model_validate({"dataset": "stock_balance", "dimensions": ["item_id"], "sql": "DROP TABLE x"})
    with pytest.raises(ValidationError):
        plan(dimensions=["item_id"], filters=[{"field": "quantity", "op": "gt", "value": 1.5}])
    with pytest.raises(ValidationError):
        plan(dimensions=["item_id; DROP TABLE x"])


@pytest.mark.security
@pytest.mark.parametrize(
    "kwargs",
    [
        {"dimensions": ["item_id", "valuation_price"]},
        {"measures": [{"field": "stock_value", "agg": "sum"}]},
        {"dimensions": ["item_id"], "filters": [{"field": "valuation_price", "op": "gt", "value": "1"}]},
        {"dimensions": ["item_id"], "filters": [{"any": [{"field": "valuation_price", "op": "is_null"}]}]},
    ],
)
def test_cost_fields_need_cost_permission(
    validator: PlanValidator, principals: dict[str, Principal], kwargs: dict[str, Any]
) -> None:
    err = rejected(validator, plan(**kwargs), principals["alpha.analyst"])
    assert err.code == "forbidden_field"
    assert err.status_code == 403


@pytest.mark.security
def test_scope_filter_is_injected(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(plan(dimensions=["warehouse_id"]), principals["alpha.north_manager"])
    scope = [f for f in vp.filters if not isinstance(f, FilterGroup) and f.origin == "scope"]
    assert len(scope) == 1
    assert scope[0].op is Op.IN
    assert scope[0].value == ["1100", "1110", "1120"]


@pytest.mark.security
def test_admin_with_all_warehouses_gets_no_scope_filter(
    validator: PlanValidator, principals: dict[str, Principal]
) -> None:
    vp = validator.validate(plan(dimensions=["warehouse_id"]), principals["alpha.admin"])
    assert all(isinstance(f, FilterGroup) or f.origin != "scope" for f in vp.filters)


@pytest.mark.security
@pytest.mark.parametrize(
    "flt",
    [
        {"field": "warehouse_id", "op": "eq", "value": "3100"},
        {"field": "warehouse_id", "op": "in", "value": ["1100", "3100"]},
        {"field": "warehouse.warehouse_id", "op": "eq", "value": "2100"},
    ],
)
def test_explicit_out_of_scope_filter_is_forbidden(
    validator: PlanValidator, principals: dict[str, Principal], flt: dict[str, Any]
) -> None:
    err = rejected(validator, plan(dimensions=["item_id"], filters=[flt]), principals["alpha.north_manager"])
    assert err.code == "forbidden_scope"
    assert err.status_code == 403


@pytest.mark.security
def test_negative_filters_cannot_widen_scope(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(
        plan(dimensions=["item_id"], filters=[{"field": "warehouse_id", "op": "ne", "value": "1100"}]),
        principals["alpha.north_manager"],
    )
    assert any(not isinstance(f, FilterGroup) and f.origin == "scope" for f in vp.filters)


@pytest.mark.security
def test_master_data_is_not_warehouse_scoped(validator: PlanValidator, principals: dict[str, Principal]) -> None:
    vp = validator.validate(
        QueryPlan(dataset="item", dimensions=["item_group"], measures=[]), principals["alpha.analyst"]
    )
    assert vp.filters == ()


def test_order_defaults_to_dimensions_for_stable_paging(
    validator: PlanValidator, principals: dict[str, Principal]
) -> None:
    vp = validator.validate(plan(dimensions=["warehouse_id", "item_id"]), principals["alpha.admin"])
    assert [o.name for o in vp.order_by] == ["warehouse_id", "item_id"]
