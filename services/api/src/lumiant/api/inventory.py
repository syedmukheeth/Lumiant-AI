"""Inventory explorer endpoints. Each request becomes a QueryPlan — no SQL is written here.

Only fields the tenant has mapped are requested, so a source without lots, ABC classes or warehouse names
(e.g. a client SAP extract) still lists its stock instead of failing on the missing columns."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from lumiant.analyses.below_reorder import BelowReorderFilters, run_below_reorder
from lumiant.auth.deps import get_container, require
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.query.plan import QueryPlan

router = APIRouter(prefix="/api", tags=["inventory"])
Reader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ))]
Codes = Annotated[list[Annotated[str, Query(max_length=64)]] | None, Query(max_length=50)]

SORTS = {
    "item_code": "item.item_code",
    "description": "item.description",
    "item_group": "item.item_group",
    "abc_class": "item.abc_class",
    "warehouse": "warehouse.name",
    "quantity": "quantity",
    "value": "stock_value",
}
BASE_COLUMNS = [
    "item_id",
    "item.item_code",
    "item.description",
    "item.item_group",
    "item.abc_class",
    "item.inventory_stage",
    "warehouse_id",
    "warehouse.name",
    "location_id",
    "lot_id",
    "stock_status",
    "quantity",
    "uom",
]
COST_COLUMNS = ["valuation_price", "stock_value", "currency"]


def _in(field: str, values: list[str] | None) -> list[dict[str, Any]]:
    return [{"field": field, "op": "in", "value": values}] if values else []


@router.get("/inventory/filters")
def filters(principal: Reader, container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    q = container.query

    mapping = q.mapping(principal.tenant_id)

    def distinct(dataset: str, field: str) -> list[str]:
        if not mapping.has_ref(dataset, field):
            return []
        plan = QueryPlan.model_validate(
            {
                "dataset": dataset,
                "dimensions": [field],
                "measures": [{"field": "item_id", "agg": "count", "alias": "n"}],
            }
        )
        return [r[field] for r in q.run_plan(plan, principal, action="inventory.filters").rows if r[field] is not None]

    wh_dims = [f for f in ("warehouse_id", "name") if mapping.has_ref("warehouse", f)]
    warehouses = (
        q.run_plan(QueryPlan(dataset="warehouse", dimensions=wh_dims), principal, action="inventory.filters").rows
        if "warehouse_id" in wh_dims
        else []
    )
    return {
        "warehouses": [{"id": w["warehouse_id"], "name": w.get("name")} for w in warehouses],
        "item_groups": distinct("item", "item_group"),
        "abc_classes": distinct("item", "abc_class"),
        "stages": distinct("item", "inventory_stage"),
        "stock_statuses": distinct("stock_balance", "stock_status"),
    }


@router.get("/inventory/balances")
def balances(
    principal: Reader,
    container: Container = Depends(get_container),  # noqa: B008
    warehouse: Codes = None,
    item_group: Codes = None,
    abc: Codes = None,
    stage: Codes = None,
    status: Codes = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    sort: Literal[
        "item_code", "description", "item_group", "abc_class", "warehouse", "quantity", "value"
    ] = "item_code",
    direction: Annotated[Literal["asc", "desc"], Query(alias="dir")] = "asc",
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    cost = principal.has(Permission.COST_READ)
    mapping = container.query.mapping(principal.tenant_id)
    dims = [c for c in BASE_COLUMNS + (COST_COLUMNS if cost else []) if mapping.has_ref("stock_balance", c)]
    # Filters on unmapped fields are passed through on purpose: the validator refuses them with a clear error.
    flt: list[dict[str, Any]] = [
        *_in("warehouse_id", warehouse),
        *_in("item.item_group", item_group),
        *_in("item.abc_class", abc),
        *_in("item.inventory_stage", stage),
        *_in("stock_status", status),
    ]
    if q and q.strip():
        term = q.strip()
        searchable = [f for f in ("item.item_code", "item.description", "item_id") if f in dims]
        flt.append({"any": [{"field": f, "op": "contains", "value": term} for f in searchable]})
    sort_field = SORTS[sort] if (sort != "value" or cost) else SORTS["item_code"]
    if sort_field not in dims:
        sort_field = next(f for f in ("item.item_code", "item_id") if f in dims)
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "dimensions": dims,
            "filters": flt,
            "order_by": [{"field": sort_field, "direction": direction}],
            "limit": limit,
            "offset": offset,
        }
    )
    result = container.query.run_plan(plan, principal, action="inventory.balances", with_total=True)
    return result.payload()


@router.get("/analyses/below-reorder")
def below_reorder(
    principal: Reader,
    container: Container = Depends(get_container),  # noqa: B008
    warehouse: Codes = None,
    item_group: Codes = None,
    abc: Codes = None,
    stage: Codes = None,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    flt = BelowReorderFilters(
        warehouses=tuple(warehouse or ()),
        item_groups=tuple(item_group or ()),
        abc_classes=tuple(abc or ()),
        stages=tuple(stage or ()),
    )
    return run_below_reorder(container.query, principal, flt, limit=limit, offset=offset).payload()
