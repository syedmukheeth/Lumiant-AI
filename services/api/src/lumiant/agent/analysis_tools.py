"""Agent tools over analyses that already back dashboard screens (S11): stock ageing, the 12-month value trend,
computed ABC and open purchase orders. Each runs the same scoped, audited analysis or typed plan as its screen."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import Field, model_validator

from lumiant.agent.tools import (
    TOOLS,
    FilterCode,
    NoArgs,
    ToolContext,
    ToolDef,
    ToolOutput,
    _amount,
    _Args,
    _col,
    _mapped,
)
from lumiant.analyses.ageing import run_ageing
from lumiant.analyses.risks import _as_of, run_abc
from lumiant.analyses.trends import run_value_trend
from lumiant.auth.permissions import Permission
from lumiant.core.errors import AppError
from lumiant.query.plan import QueryPlan


# ------------------------------------------------------------------------------------------ stock ageing
def _per_currency(values: dict[str, str] | None) -> str:
    return "; ".join(f"{cur} {_amount(v)}".strip() for cur, v in sorted((values or {}).items()))


def stock_ageing(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    res = run_ageing(ctx.query, ctx.principal)
    cost = bool(res["value_visible"])
    rows = [
        {"bucket": b["label"], "pairs": b["pairs"], **({"value": _per_currency(b.get("value"))} if cost else {})}
        for b in res["buckets"]
    ]
    old = [b for b in res["buckets"] if b["bucket"] in ("365+", "never")]
    n_old = sum(int(b["pairs"]) for b in old)
    answer = (
        f"{n_old} item–warehouse pairs with stock on hand have not been issued for over 365 days or were never "
        f"issued (as of {res['as_of']})."
    )
    if cost and old:
        parts = [f"{b['label'].lower()}: {_per_currency(b.get('value'))}" for b in old if b.get("value")]
        if parts:
            answer += " Value held — " + "; ".join(parts) + "."
    columns = [_col("bucket", "Days since last issue"), _col("pairs", "Item–warehouse pairs", "int")]
    if cost:
        columns.append(_col("value", "Value"))
    block = {"type": "table", "title": "Stock ageing", "columns": columns, "rows": rows}
    return ToolOutput(
        "stock_ageing",
        "Stock ageing",
        answer,
        [block],
        None,
        res["warnings"],
        ["Which items have not moved in a year?", "How can we free up cash tied in stock?"],
        {"buckets": rows, "as_of": res["as_of"], "rule": res["rule"], "old_pairs": n_old},
    )


# ------------------------------------------------------------------------------------------ value trend
class TrendArgs(_Args):
    months: int = Field(default=12, ge=1, le=24, description="Months of history, 1-24")


def value_trend(ctx: ToolContext, a: TrendArgs) -> ToolOutput:
    res = run_value_trend(ctx.query, ctx.principal, months=a.months)
    rows: list[dict[str, Any]] = []
    sentences = []
    for s in res["series"]:
        cur, points = s["currency"], s["points"]
        for p in points:
            rows.append(
                {
                    "period": p["period"],
                    "currency": cur,
                    "value": p["value"],
                    "receipts_value": p["receipts_value"],
                    "issues_value": p["issues_value"],
                }
            )
        if len(points) >= 2 and points[0]["value"] is not None and points[-1]["value"] is not None:
            sentences.append(
                f"Inventory value in {cur} was {_amount(points[0]['value'])} at the end of {points[0]['period']} and is "
                f"{_amount(points[-1]['value'])} now."
            )
    answer = " ".join(sentences) or "There is no movement history to rebuild the value trend from."
    table = {
        "type": "table",
        "title": f"Inventory value, last {a.months} months",
        "columns": [
            _col("period", "Month"),
            _col("currency", "Currency"),
            _col("value", "Month-end value", "money"),
            _col("receipts_value", "Receipts", "money"),
            _col("issues_value", "Issues", "money"),
        ],
        "rows": rows,
    }
    chart = {
        "type": "chart",
        "variant": "line",
        "title": f"Inventory value, last {a.months} months",
        "x_key": "period",
        "series": [{"key": "value", "label": "Month-end value", "kind": "money", "unit_key": "currency"}],
        "rows": rows,
    }
    return ToolOutput(
        "value_trend",
        "Value trend",
        answer,
        [table, chart],
        None,
        res["warnings"],
        ["Where is cash tied up in stock?", "Show inventory value by warehouse"],
        {"rows": rows, "rule": res["rule"], "as_of": res["as_of"]},
    )


# ------------------------------------------------------------------------------------------ computed ABC
class AbcArgs(_Args):
    a_pct: int = Field(ge=1, le=99, description="Cumulative value share that ends class A, in percent (no default)")
    b_pct: int = Field(ge=2, le=100, description="Cumulative value share that ends class B, in percent (no default)")
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$", description="Needed when values are in several")

    @model_validator(mode="after")
    def _order(self) -> AbcArgs:
        if self.b_pct <= self.a_pct:
            raise ValueError("b_pct must be above a_pct")
        return self


def computed_abc(ctx: ToolContext, a: AbcArgs) -> ToolOutput:
    res = run_abc(
        ctx.query,
        ctx.principal,
        a_cutoff=Decimal(a.a_pct) / 100,
        b_cutoff=Decimal(a.b_pct) / 100,
        currency=a.currency,
    )
    counts = {cls: sum(row.values()) for cls, row in res["matrix"].items()}
    answer = (
        f"With A up to {a.a_pct}% and B up to {a.b_pct}% of the {res['currency'] or ''} value, "
        + ", ".join(f"{n} items are class {cls}" for cls, n in sorted(counts.items()))
        + "."
    )
    if res["assigned_available"]:
        answer += f" {res['differences']} items differ from the class assigned in the source."
    rows = [
        {
            "item_id": i["item_id"],
            "value": i["value"],
            "computed": i["computed"],
            "assigned": i["assigned"] or "",
            "differs": "yes" if i["differs"] else "",
        }
        for i in res["items"][:25]
    ]
    block = {
        "type": "table",
        "title": f"Computed ABC (A ≤ {a.a_pct}%, B ≤ {a.b_pct}%)",
        "columns": [
            _col("item_id", "Item"),
            _col("value", "Value", "money"),
            _col("computed", "Computed"),
            _col("assigned", "Assigned"),
            _col("differs", "Differs"),
        ],
        "rows": rows,
    }
    data = {"counts": counts, "differences": res["differences"], "item_count": res["item_count"], "rows": rows}
    return ToolOutput(
        "computed_abc", "Computed ABC", answer, [block], res.get("provenance"), res.get("warnings", []), [], data
    )


# ------------------------------------------------------------------------------------------ open purchase orders
class OpenPoArgs(_Args):
    item_id: FilterCode | None = Field(default=None, description="Only this item")
    supplier_id: FilterCode | None = Field(default=None, description="Only this supplier")
    warehouse_id: FilterCode | None = Field(default=None, description="Only this warehouse")
    overdue_only: bool = Field(default=False, description="Only lines past their expected date")


def open_purchase_orders(ctx: ToolContext, a: OpenPoArgs) -> ToolOutput:
    mapping = ctx.query.mapping(ctx.principal.tenant_id)
    if not mapping.is_mapped("purchase_record") or mapping.field("purchase_record", "status") is None:
        raise AppError("not_mapped", "Purchase orders are not in this organisation's data.", 409)
    as_of = _as_of(ctx.query, ctx.principal.tenant_id).isoformat()
    filters: list[dict[str, Any]] = [{"field": "status", "op": "eq", "value": "OPEN"}]
    for key in ("item_id", "supplier_id", "warehouse_id"):
        if getattr(a, key):
            filters.append({"field": key, "op": "eq", "value": getattr(a, key)})
    overdue = {"field": "expected_date", "op": "lt", "value": as_of}
    has_expected = mapping.field("purchase_record", "expected_date") is not None
    if a.overdue_only and has_expected:
        filters.append(overdue)

    def count(extra: list[dict[str, Any]]) -> int:
        plan = QueryPlan.model_validate(
            {
                "dataset": "purchase_record",
                "measures": [{"field": "po_id", "agg": "count", "alias": "n"}],
                "filters": filters + extra,
            }
        )
        rows = ctx.query.run_plan(plan, ctx.principal, action="agent:open_purchase_orders").rows
        return int(rows[0]["n"]) if rows else 0

    total = count([])
    late = count([overdue]) if has_expected and not a.overdue_only else (total if a.overdue_only else 0)
    wanted = ["po_id", "line", "item_id", "supplier_id", "warehouse_id", "expected_date", "status"]
    if ctx.principal.has(Permission.COST_READ):
        wanted += ["unit_price", "currency"]
    dims = [d for d in _mapped(ctx, "purchase_record", wanted) if mapping.field("purchase_record", d) is not None]
    qty_field = "open_quantity" if mapping.field("purchase_record", "open_quantity") is not None else "quantity"
    plan = QueryPlan.model_validate(
        {
            "dataset": "purchase_record",
            "dimensions": dims,
            "measures": [{"field": qty_field, "agg": "sum", "alias": "open_qty"}],
            "filters": filters,
            "order_by": [{"field": "expected_date" if has_expected else dims[0], "direction": "asc"}],
            "limit": 50,
        }
    )
    res = ctx.query.run_plan(plan, ctx.principal, action="agent:open_purchase_orders")
    payload = res.payload()
    what = "overdue open purchase-order lines" if a.overdue_only else "open purchase-order lines"
    answer = f"{total} {what} in your scope."
    if has_expected and not a.overdue_only:
        answer += f" {late} of them are past their expected date (as of {as_of})."
    if res.truncated:
        answer += f" The table shows the first {len(res.rows)}, earliest expected first."
    labels = {
        "po_id": ("Order", "text"),
        "line": ("Line", "text"),
        "item_id": ("Item", "text"),
        "supplier_id": ("Supplier", "text"),
        "warehouse_id": ("Warehouse", "text"),
        "expected_date": ("Expected", "date"),
        "status": ("Status", "text"),
        "unit_price": ("Unit price", "money"),
        "currency": ("Currency", "text"),
    }
    columns = [_col(d, *labels[d]) for d in dims] + [_col("open_qty", "Open quantity", "qty"), _col("uom", "Unit")]
    block = {"type": "table", "title": "Open purchase orders", "columns": columns, "rows": payload["data"]}
    data = {**payload, "open_lines": total, "overdue_lines": late, "as_of": as_of}
    return ToolOutput(
        "open_purchase_orders",
        "Open purchase orders",
        answer,
        [block],
        payload["provenance"],
        [w.__dict__ for w in res.warnings if w.code != "auto_grouped"],
        ["Which items are below reorder level?"],
        data,
    )


ANALYSIS_TOOLS = (
    ToolDef(
        "stock_ageing",
        "Stock on hand grouped by days since each item last left its warehouse (0-90, 91-180, 181-365, over 365 "
        "days, never issued): pairs per bucket, and value per currency with cost access.",
        NoArgs,
        (Permission.INVENTORY_READ,),
        stock_ageing,
    ),
    ToolDef(
        "value_trend",
        "Month-end inventory value for the last 1-24 months (default 12), rebuilt from movements at current prices, "
        "with the value received and issued each month, per currency. Use for trends and 'over time' questions.",
        TrendArgs,
        (Permission.INVENTORY_READ, Permission.COST_READ),
        value_trend,
    ),
    ToolDef(
        "computed_abc",
        "Classify items A/B/C by on-hand value with cutoffs the user chooses (there are no defaults: ask for them), "
        "and compare with the class assigned in the source.",
        AbcArgs,
        (Permission.INVENTORY_READ, Permission.COST_READ),
        computed_abc,
    ),
    ToolDef(
        "open_purchase_orders",
        "Open purchase-order lines (optionally for one item, supplier or warehouse, or only overdue ones), earliest "
        "expected first, with how many are past their expected date.",
        OpenPoArgs,
        (Permission.INVENTORY_READ,),
        open_purchase_orders,
    ),
)
TOOLS.update({t.name: t for t in ANALYSIS_TOOLS})
