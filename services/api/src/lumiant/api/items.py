"""Material 360 (V4, docs/05-plan/PRODUCT_V3_PLAN.md §5.1): everything about one item on one screen.

Every section is a validated plan through the query service, so warehouse scope is injected, cost fields need cost
rights, and each section carries its own provenance. A section whose data is not mapped, or that the caller may not
see, is reported as unavailable with the reason rather than failing the whole view.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path

from lumiant.auth.deps import get_container, require
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.core.errors import AppError, NotFoundError
from lumiant.query.plan import QueryPlan

router = APIRouter(prefix="/api/items", tags=["items"])
Reader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ))]
ItemId = Annotated[str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-/ ]+$")]

ITEM_FIELDS = (
    "item_id",
    "item_code",
    "description",
    "item_group",
    "inventory_stage",
    "abc_class",
    "base_uom",
    "status",
    "lot_tracked",
    "shelf_life_days",
    "default_supplier_id",
    "manufacturer",
    "lifecycle_status",
    "critical",
)


def _section(container: Container, principal: Principal, spec: dict[str, Any], action: str) -> dict[str, Any]:
    q = container.query
    mapping = q.mapping(principal.tenant_id)
    ds = spec["dataset"]
    if not mapping.is_mapped(ds):
        return {"available": False, "reason": "Not mapped for this workspace."}
    spec = {**spec, "dimensions": [d for d in spec.get("dimensions", []) if mapping.has_ref(ds, d)]}
    spec["measures"] = [m for m in spec.get("measures", []) if mapping.has_ref(ds, m["field"])]
    spec["order_by"] = [
        o
        for o in spec.get("order_by", [])
        if o["field"] in spec["dimensions"] or any(m["alias"] == o["field"] for m in spec["measures"])
    ]
    if not spec["dimensions"] and not spec["measures"]:
        return {"available": False, "reason": "Not mapped for this workspace."}
    try:
        res = q.run_plan(QueryPlan.model_validate(spec), principal, action=action)
    except AppError as exc:
        if exc.code in ("forbidden_field", "field_not_available", "dataset_not_available", "forbidden_scope"):
            return {"available": False, "reason": exc.message}
        raise
    payload = res.payload()
    return {"available": True, "rows": payload["data"], "truncated": res.truncated, "provenance": payload["provenance"]}


@router.get("/{item_id}")
def item_360(item_id: ItemId, principal: Reader, container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    this = {"field": "item_id", "op": "eq", "value": item_id}
    master = _section(
        container,
        principal,
        {"dataset": "item", "dimensions": list(ITEM_FIELDS), "filters": [this], "limit": 1},
        "item:master",
    )
    if master.get("available") and not master["rows"]:
        raise NotFoundError("not_found", "No item with that id.")
    cost = principal.has(Permission.COST_READ)
    stock_measures = [{"field": "quantity", "agg": "sum", "alias": "quantity"}]
    if cost:
        stock_measures.append({"field": "stock_value", "agg": "sum", "alias": "value"})
    sections = {
        "stock": _section(
            container,
            principal,
            {
                "dataset": "stock_balance",
                "dimensions": ["warehouse_id", "warehouse.name", "uom"],
                "measures": stock_measures,
                "filters": [this],
                "order_by": [{"field": "quantity", "direction": "desc"}],
                "limit": 50,
            },
            "item:stock",
        ),
        "lots": _section(
            container,
            principal,
            {
                "dataset": "stock_balance",
                "dimensions": ["lot_id", "lot.expiry_date", "warehouse_id", "quantity", "uom"],
                "filters": [
                    this,
                    {"field": "quantity", "op": "gt", "value": "0"},
                    {"field": "lot_id", "op": "is_not_null"},
                ],
                "order_by": [{"field": "lot.expiry_date"}],
                "limit": 30,
            },
            "item:lots",
        ),
        "movements": _section(
            container,
            principal,
            {
                "dataset": "inventory_transaction",
                "dimensions": ["posting_date", "txn_type", "warehouse_id", "quantity", "uom", "txn_id"],
                "filters": [this],
                "order_by": [{"field": "posting_date", "direction": "desc"}, {"field": "txn_id", "direction": "desc"}],
                "limit": 20,
            },
            "item:movements",
        ),
        "policies": _section(
            container,
            principal,
            {
                "dataset": "reorder_policy",
                "dimensions": ["warehouse_id", "reorder_level", "min_stock", "max_stock"],
                "filters": [this],
                "limit": 50,
            },
            "item:policies",
        ),
        "purchases": _section(
            container,
            principal,
            {
                "dataset": "purchase_record",
                "dimensions": ["po_id", "order_date", "status", "supplier_id", "warehouse_id", "quantity", "uom"],
                "filters": [this],
                "order_by": [{"field": "order_date", "direction": "desc"}, {"field": "po_id"}],
                "limit": 20,
            },
            "item:purchases",
        ),
    }
    return {"item_id": item_id, "master": master, **sections, "cost_visible": cost}
