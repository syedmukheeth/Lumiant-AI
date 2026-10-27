"""The agent's fixed tool catalog (ADR-0002). The model can only pick one of these and fill typed arguments;
every tool runs through the same validated, scope-injected, audited query path as the dashboard."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lumiant.analyses.below_reorder import BelowReorderFilters, run_below_reorder
from lumiant.analyses.risks import run_cost_comparison, run_data_quality, run_dormant, run_expiring
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError
from lumiant.query.plan import QueryPlan
from lumiant.query.results import QueryResult
from lumiant.query.service import QueryService

Block = dict[str, Any]


@dataclass
class ToolContext:
    query: QueryService
    principal: Principal


@dataclass
class ToolOutput:
    tool: str
    title: str
    answer: str
    blocks: list[Block] = field(default_factory=list)
    provenance: dict[str, Any] | None = None
    warnings: list[dict[str, str]] = field(default_factory=list)
    follow_ups: list[str] = field(default_factory=list)
    data: Any = None  # structured evidence used for grounding and (capped) model context
    ok: bool = True  # False when the tool did not run (denied, bad arguments, failed)


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NoArgs(_Args):
    pass


class ItemArgs(_Args):
    item_id: str = Field(min_length=1, max_length=64, description="Exact item id from the item master")


class CostArgs(ItemArgs):
    warehouse_id: str = Field(min_length=1, max_length=64, description="Exact warehouse id")


class StockByArgs(_Args):
    dimension: str = Field(pattern=r"^(warehouse|item_group|stage|abc)$", description="Grouping")
    measure: str = Field(default="value", pattern=r"^(value|quantity)$", description="Value needs cost access")


class TopArgs(_Args):
    limit: int = Field(default=10, ge=1, le=50)


class DaysArgs(_Args):
    days: int = Field(default=270, ge=1, le=3650, description="Window in days")


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    args: type[_Args]
    permissions: tuple[Permission, ...]
    run: Callable[[ToolContext, Any], ToolOutput]

    def schema(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.args.model_json_schema()}


def _warn(result: QueryResult) -> list[dict[str, str]]:
    return [w.__dict__ for w in result.warnings if w.code not in ("auto_grouped",)]


def _col(key: str, label: str, kind: str = "text") -> dict[str, str]:
    return {"key": key, "label": label, "kind": kind}


def _first_money(rows: list[dict[str, Any]], key: str) -> str:
    return f"{rows[0].get('currency', '')} {rows[0][key]}".strip()


# ------------------------------------------------------------------------------------------ item lookup
def find_items(ctx: ToolContext, text: str, limit: int = 6) -> list[dict[str, Any]]:
    """Fuzzy item lookup over code and description (case-insensitive substring). Scope rules still apply."""
    plan = QueryPlan.model_validate(
        {
            "dataset": "item",
            "dimensions": ["item_id", "item_code", "description"],
            "filters": [
                {
                    "any": [
                        {"field": "item_id", "op": "eq", "value": text},
                        {"field": "item_code", "op": "contains", "value": text},
                        {"field": "description", "op": "contains", "value": text},
                    ]
                }
            ],
            "limit": limit,
        }
    )
    return ctx.query.run_plan(plan, ctx.principal, action="agent:resolve_item").rows


def visible_warehouses(ctx: ToolContext) -> list[dict[str, Any]]:
    plan = QueryPlan.model_validate({"dataset": "warehouse", "dimensions": ["warehouse_id", "name"]})
    return ctx.query.run_plan(plan, ctx.principal, action="agent:resolve_warehouse").rows


# ------------------------------------------------------------------------------------------ handlers
def stock_position(ctx: ToolContext, a: ItemArgs) -> ToolOutput:
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "dimensions": ["warehouse_id", "warehouse.name"],
            "measures": [{"field": "quantity", "agg": "sum", "alias": "qty"}],
            "filters": [
                {"field": "item_id", "op": "eq", "value": a.item_id},
                {"field": "quantity", "op": "gt", "value": "0"},
            ],
            "order_by": [{"field": "qty", "direction": "desc"}],
        }
    )
    res = ctx.query.run_plan(plan, ctx.principal, action="agent:stock_position")
    payload = res.payload()
    rows = payload["data"]
    if not rows:
        answer = f"I found no stock of item {a.item_id} in the warehouses you can see."
    else:
        top = rows[0]
        answer = (
            f"Item {a.item_id} is held in {len(rows)} warehouse{'s' if len(rows) != 1 else ''}. "
            f"The largest holding is {top['qty']} {top['uom']} in {top['warehouse.name']} ({top['warehouse_id']})."
        )
    block = {
        "type": "table",
        "title": f"Stock of {a.item_id} by warehouse",
        "columns": [_col("warehouse_id", "Warehouse"), _col("warehouse.name", "Name"), _col("qty", "On hand", "qty")],
        "rows": rows,
    }
    return ToolOutput(
        "stock_position", "Stock position", answer, [block], payload["provenance"], _warn(res), data=payload
    )


_DIMS = {
    "warehouse": (["warehouse_id", "warehouse.name"], "warehouse.name", "Warehouse"),
    "item_group": (["item.item_group"], "item.item_group", "Item group"),
    "stage": (["item.inventory_stage"], "item.inventory_stage", "Stage"),
    "abc": (["item.abc_class"], "item.abc_class", "ABC class (assigned)"),
}


def stock_by(ctx: ToolContext, a: StockByArgs) -> ToolOutput:
    dims, label_key, label = _DIMS[a.dimension]
    valued = a.measure == "value"
    if valued and not ctx.principal.has(Permission.COST_READ):
        raise AppError("forbidden_field", "Your role cannot view inventory values; I can show quantities instead.", 403)
    measure = {"field": "stock_value" if valued else "quantity", "agg": "sum", "alias": "total"}
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "dimensions": dims,
            "measures": [measure],
            "order_by": [{"field": "total", "direction": "desc"}],
            "limit": 50,
        }
    )
    res = ctx.query.run_plan(plan, ctx.principal, action="agent:stock_by")
    payload = res.payload()
    rows = payload["data"]
    unit_key = "currency" if valued else "uom"
    kind = "money" if valued else "qty"
    if not rows:
        answer = "There is no stock in your scope."
    else:
        top = rows[0]
        units = sorted({str(r[unit_key]) for r in rows})
        answer = f"The highest {label.lower()} is {top[label_key] or 'not set'} with {top[unit_key]} {top['total']}."
        if len(units) > 1:
            answer += f" Results are shown separately per {'currency' if valued else 'unit'} ({', '.join(units)}) and never added together."
    blocks = [
        {
            "type": "bar",
            "title": f"{'Value' if valued else 'Quantity'} by {label.lower()}",
            "label_key": label_key,
            "value_key": "total",
            "kind": kind,
            "unit_key": unit_key,
            "rows": rows,
        }
    ]
    follow = ["Show the highest-value items"] if valued else []
    return ToolOutput(
        "stock_by", "Stock by " + label.lower(), answer, blocks, payload["provenance"], _warn(res), follow, payload
    )


def top_value_items(ctx: ToolContext, a: TopArgs) -> ToolOutput:
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "dimensions": ["item_id", "item.item_code", "item.description"],
            "measures": [{"field": "stock_value", "agg": "sum", "alias": "value"}],
            "order_by": [{"field": "value", "direction": "desc"}],
            "limit": a.limit,
        }
    )
    res = ctx.query.run_plan(plan, ctx.principal, action="agent:top_value_items")
    payload = res.payload()
    rows = payload["data"]
    answer = (
        f"The highest-value item is {rows[0]['item.item_code']} ({rows[0]['item.description']}) at {_first_money(rows, 'value')}."
        if rows
        else "There are no valued items in your scope."
    )
    block = {
        "type": "table",
        "title": f"Top {len(rows)} items by on-hand value",
        "columns": [
            _col("item.item_code", "Item"),
            _col("item.description", "Description"),
            _col("value", "Value", "money"),
        ],
        "rows": rows,
    }
    return ToolOutput(
        "top_value_items", "Highest-value items", answer, [block], payload["provenance"], _warn(res), data=payload
    )


def _analysis_output(
    tool: str, title: str, res: QueryResult, columns: list[dict[str, str]], answer: str, follow: list[str] | None = None
) -> ToolOutput:
    payload = res.payload()
    block = {"type": "table", "title": title, "columns": columns, "rows": payload["data"]}
    return ToolOutput(tool, title, answer, [block], payload["provenance"], _warn(res), follow or [], payload)


_ITEM = _col("item_code", "Item")
_DESC = _col("description", "Description")


def below_reorder(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    res = run_below_reorder(ctx.query, ctx.principal, BelowReorderFilters(), limit=15, offset=0)
    s = res.summary or {}
    rows = res.payload()["data"]
    answer = f"{s['flagged']} item–warehouse pairs are below their reorder level."
    if rows:
        r = rows[0]
        answer += f" The lowest coverage is {r['item_code']} in {r['warehouse_id']}: {r['on_hand']} on hand against a reorder level of {r['reorder_level']}."
    if s.get("pairs_without_policy"):
        answer += f" {s['pairs_without_policy']} stocked pairs have no reorder policy, so they cannot be assessed."
    cols = [
        _ITEM,
        _DESC,
        _col("warehouse_id", "Warehouse"),
        _col("on_hand", "On hand", "qty"),
        _col("reorder_level", "Reorder level", "qty"),
        _col("shortfall", "Shortfall", "qty"),
    ]
    return _analysis_output(
        "below_reorder", "Items below reorder level", res, cols, answer, ["Which items are in excess?"]
    )


def excess_stock(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    res = run_below_reorder(ctx.query, ctx.principal, BelowReorderFilters(), limit=15, offset=0, mode="excess")
    s = res.summary or {}
    rows = res.payload()["data"]
    answer = f"{s['flagged']} item–warehouse pairs hold more than their maximum stock policy."
    if rows:
        answer += f" The largest is {rows[0]['item_code']} in {rows[0]['warehouse_id']}: {rows[0]['on_hand']} on hand against a maximum of {rows[0]['max_stock']}."
    cols = [
        _ITEM,
        _DESC,
        _col("warehouse_id", "Warehouse"),
        _col("on_hand", "On hand", "qty"),
        _col("max_stock", "Maximum", "qty"),
        _col("excess", "Excess", "qty"),
    ]
    return _analysis_output("excess_stock", "Excess stock", res, cols, answer)


def dormant(ctx: ToolContext, a: DaysArgs) -> ToolOutput:
    res = run_dormant(ctx.query, ctx.principal, days=a.days, limit=15, offset=0)
    s = res.summary or {}
    answer = (
        f"{s['flagged']} item–warehouse pairs have stock but no issue in the last {a.days} days (as of {s['as_of']})."
    )
    cols = [
        _ITEM,
        _DESC,
        _col("warehouse_id", "Warehouse"),
        _col("on_hand", "On hand", "qty"),
        _col("last_issue", "Last issue", "date"),
        _col("days_since_issue", "Days idle", "int"),
    ]
    return _analysis_output("dormant", f"Stock with no issue in {a.days} days", res, cols, answer)


def expiring_lots(ctx: ToolContext, a: DaysArgs) -> ToolOutput:
    res = run_expiring(ctx.query, ctx.principal, days=min(a.days, 3650), limit=15)
    s = res.summary or {}
    answer = f"{s['expired']} lots on hand have already expired and {s['expiring']} more expire within {a.days} days."
    cols = [
        _col("item.item_code", "Item"),
        _col("warehouse_id", "Warehouse"),
        _col("lot_id", "Lot"),
        _col("quantity", "Quantity", "qty"),
        _col("lot.expiry_date", "Expires", "date"),
        _col("days_to_expiry", "Days left", "int"),
    ]
    return _analysis_output("expiring_lots", "Lots nearing or past expiry", res, cols, answer)


def data_quality(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    dq = run_data_quality(ctx.query, ctx.principal)
    issues = [c for c in dq["checks"] if c["status"] == "issue"]
    answer = (
        f"{len(issues)} of {len(dq['checks'])} master-data checks found gaps among {dq['total_items']} items."
        if issues
        else f"No gaps found by the {len(dq['checks'])} master-data checks."
    )
    if issues:
        worst = max(issues, key=lambda c: c["count"] or 0)
        answer += f" The largest is: {worst['title']} ({worst['count']})."
    rows = [{"check": c["title"], "status": c["status"], "count": c["count"]} for c in dq["checks"]]
    block = {
        "type": "table",
        "title": "Master-data checks",
        "columns": [_col("check", "Check"), _col("status", "Status"), _col("count", "Count", "int")],
        "rows": rows,
    }
    return ToolOutput(
        "data_quality",
        "Master-data quality",
        answer,
        [block],
        None,
        dq["warnings"],
        data={"checks": rows, "total_items": dq["total_items"]},
    )


def cost_comparison(ctx: ToolContext, a: CostArgs) -> ToolOutput:
    res = run_cost_comparison(ctx.query, ctx.principal, item_id=a.item_id, warehouse_id=a.warehouse_id)
    m, cur = res["methods"], res["currency"] or ""
    rows = []
    for key, label in (("moving_weighted_average", "Moving weighted average"), ("fifo", "FIFO (remaining layers)")):
        if m.get(key):
            rows.append({"method": label, "unit_cost": m[key]["unit_cost"], "value": m[key]["value"], "currency": cur})
    if m.get("latest_receipt_cost"):
        rows.append(
            {
                "method": "Latest receipt cost",
                "unit_cost": m["latest_receipt_cost"]["unit_cost"],
                "value": None,
                "currency": cur,
            }
        )
    if m.get("latest_valid_purchase_price"):
        rows.append(
            {
                "method": "Latest valid purchase price",
                "unit_cost": m["latest_valid_purchase_price"]["unit_price"],
                "value": None,
                "currency": cur,
            }
        )
    src = m["source_valuation"]
    rows.append({"method": "Source valuation", "unit_cost": src["unit_cost"], "value": src["value"], "currency": cur})
    parts = [f"{r['method'].lower()} {cur} {r['unit_cost']}" for r in rows if r["unit_cost"]]
    answer = f"For item {a.item_id} in {a.warehouse_id}: " + "; ".join(parts) + "."
    rec = res["reconciliation"]
    if rec["status"] == "match":
        answer += " The recomputed average matches the source valuation."
    elif rec["status"] == "differs":
        answer += f" The recomputed average differs from the source valuation by {cur} {rec['difference_unit_cost']} per unit."
    block = {
        "type": "table",
        "title": "Cost comparison (draft definitions)",
        "columns": [_col("method", "Method"), _col("unit_cost", "Unit cost", "money"), _col("value", "Value", "money")],
        "rows": rows,
    }
    return ToolOutput(
        "cost_comparison", "Cost comparison", answer, [block], res["provenance"], res["warnings"], data=res
    )


def special_storage(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    plan = QueryPlan.model_validate(
        {
            "dataset": "item",
            "dimensions": [
                "item_code",
                "description",
                "item_group",
                "storage_temp_min",
                "storage_temp_max",
                "flammability_class",
            ],
            "filters": [
                {
                    "any": [
                        {"field": "storage_temp_min", "op": "is_not_null"},
                        {"field": "flammability_class", "op": "is_not_null"},
                    ]
                }
            ],
            "order_by": [{"field": "item_code"}],
            "limit": 15,
        }
    )
    res = ctx.query.run_plan(plan, ctx.principal, action="agent:special_storage", with_total=True)
    payload = res.payload()
    total = payload["page"]["total"]
    answer = (
        f"{total} items have recorded special storage requirements (a temperature range or a flammability class). "
        "This only reflects what is recorded in the item master; I do not infer requirements from item names."
    )
    cols = [
        _col("item_code", "Item"),
        _col("description", "Description"),
        _col("storage_temp_min", "Min °C", "int"),
        _col("storage_temp_max", "Max °C", "int"),
        _col("flammability_class", "Flammability"),
    ]
    block = {
        "type": "table",
        "title": "Items with recorded storage requirements",
        "columns": cols,
        "rows": payload["data"],
    }
    return ToolOutput(
        "special_storage", "Special storage", answer, [block], payload["provenance"], _warn(res), data=payload
    )


TOOLS: dict[str, ToolDef] = {
    t.name: t
    for t in (
        ToolDef(
            "stock_position",
            "On-hand quantity of one item by warehouse.",
            ItemArgs,
            (Permission.INVENTORY_READ,),
            stock_position,
        ),
        ToolDef(
            "stock_by",
            "Stock value or quantity grouped by warehouse, item group, stage or assigned ABC class.",
            StockByArgs,
            (Permission.INVENTORY_READ,),
            stock_by,
        ),
        ToolDef(
            "top_value_items",
            "The highest-value items by on-hand value.",
            TopArgs,
            (Permission.INVENTORY_READ, Permission.COST_READ),
            top_value_items,
        ),
        ToolDef(
            "below_reorder",
            "Items below their customer-defined reorder level.",
            NoArgs,
            (Permission.INVENTORY_READ,),
            below_reorder,
        ),
        ToolDef(
            "excess_stock",
            "Items above their customer-defined maximum stock.",
            NoArgs,
            (Permission.INVENTORY_READ,),
            excess_stock,
        ),
        ToolDef(
            "dormant",
            "Stock with no issue movement within a number of days.",
            DaysArgs,
            (Permission.INVENTORY_READ,),
            dormant,
        ),
        ToolDef(
            "expiring_lots",
            "Lots on hand that are expired or expire within a number of days.",
            DaysArgs,
            (Permission.INVENTORY_READ,),
            expiring_lots,
        ),
        ToolDef("data_quality", "Master-data completeness checks.", NoArgs, (Permission.INVENTORY_READ,), data_quality),
        ToolDef(
            "cost_comparison",
            "Compare costing methods for one item in one warehouse.",
            CostArgs,
            (Permission.INVENTORY_READ, Permission.COST_READ),
            cost_comparison,
        ),
        ToolDef(
            "special_storage",
            "Items with recorded special storage requirements.",
            NoArgs,
            (Permission.INVENTORY_READ,),
            special_storage,
        ),
    )
}


def tools_for(principal: Principal) -> list[ToolDef]:
    """Only tools the principal may use are ever shown to a model."""
    return [t for t in TOOLS.values() if all(principal.has(p) for p in t.permissions)]


def decimal_sum(rows: list[dict[str, Any]], key: str) -> Decimal:
    return sum((Decimal(str(r[key])) for r in rows), Decimal(0))
