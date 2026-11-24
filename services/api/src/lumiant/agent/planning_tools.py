"""Planning tools for the assistant: fulfilment, material plan, BOM, suppliers, commitments, duplicates, lifecycle.

Each tool calls `PlanningService` (the same code the API uses) and words its answer only from the returned data, so
the grounding check can trace every number. Answers are recommendations; nothing is ordered, approved or changed.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import Field

from lumiant.agent.tools import Block, NoArgs, ToolContext, ToolDef, ToolOutput, _Args, _col
from lumiant.auth.permissions import Permission
from lumiant.planning.service import POLICIES, PlanningService

Code = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-/ ]+$")


class OrderArgs(_Args):
    order_id: str | None = Field(
        default=None, min_length=1, max_length=64, description="Customer order id; omit for all open orders"
    )


class CommitmentArgs(_Args):
    order_id: str | None = Field(
        default=None, min_length=1, max_length=64, description="Customer order or order line (SO-1001 or SO-1001/10)"
    )
    hint: str | None = Field(
        default=None, max_length=300, description="The user's words, to pick the order by customer or product named"
    )


def _pick_by_hint(rows: list[dict[str, Any]], hint: str | None) -> list[dict[str, Any]]:
    """At-risk lines whose customer, item or item word (FG-PUMP-100 -> "pump") the user named."""
    if not hint:
        return []
    text = hint.upper()
    words = set(re.findall(r"[A-Z0-9]+", text))
    picked = []
    for r in rows:
        cust, item = str(r["customer_id"]).upper(), str(r["item_id"]).upper()
        parts = {w for w in re.split(r"[-_./ ]", item) if len(w) >= 4 and w.isalpha()}
        cust_parts = {w for w in re.split(r"[-_./ ]", cust) if len(w) >= 4 and w.isalpha() and w != "CUST"}
        if cust in text or item in text or parts & words or cust_parts & words:
            picked.append(r)
    return picked


class ItemFilterArgs(_Args):
    item_id: str | None = Field(default=None, min_length=1, max_length=64, description="Only this item; omit for all")


class BomArgs(_Args):
    item_id: str = Field(min_length=1, max_length=64, description="Item to explode")
    quantity: Decimal = Field(default=Decimal(1), gt=0, le=Decimal("1e9"))


class SupplierArgs(_Args):
    item_id: str = Field(min_length=1, max_length=64, description="Item to source")
    quantity: Decimal = Field(gt=0, le=Decimal("1e9"), description="Quantity needed")
    need_date: date | None = Field(default=None, description="Date the material is needed")
    policy: str = Field(default="balanced", pattern="^(" + "|".join(POLICIES) + ")$", description="Ranking policy")


class ScopeArgs(_Args):
    question: str = Field(min_length=1, max_length=1000)


def _svc(ctx: ToolContext) -> PlanningService:
    return PlanningService(ctx.query)


def _table(title: str, cols: list[tuple[str, str, str]], rows: list[dict[str, Any]]) -> Block:
    return {"type": "table", "title": title, "columns": [_col(k, label, kind) for k, label, kind in cols], "rows": rows}


def _blockers(issues: list[dict[str, Any]]) -> list[str]:
    return [i["message"] for i in issues if i.get("severity") in ("blocker", "warning")][:3]


def order_fulfilment(ctx: ToolContext, a: OrderArgs) -> ToolOutput:
    out = _svc(ctx).fulfilment(ctx.principal, order_id=a.order_id)
    lines = out["lines"]
    late = [ln for ln in lines if not ln["on_time"]]
    if not late:
        answer = f"All {len(lines)} open order line{'s' if len(lines) != 1 else ''} can be delivered on time."
    else:
        worst = sorted(late, key=lambda ln: (ln["ready"] is not None, -(ln["late_days"] or 0)))[0]
        when = (
            f"is ready {worst['ready']}, {worst['late_days']} working days after its due date {worst['due']}"
            if worst["ready"]
            else f"cannot be dated (due {worst['due']})"
        )
        answer = (
            f"{len(lines) - len(late)} of {len(lines)} open order lines can be delivered on time. "
            f"{worst['key']} ({worst['quantity']} {worst['item_id']}) {when}"
            + (f": {worst['reasons'][0]}" if worst["reasons"] else ".")
        )
    cols = [
        ("key", "Order line", "text"),
        ("item_id", "Item", "text"),
        ("quantity", "Qty", "qty"),
        ("due", "Due", "date"),
        ("from_stock", "From stock", "qty"),
        ("from_receipts", "Open POs", "qty"),
        ("from_alternates", "Alternates", "qty"),
        ("from_planned", "To make / buy", "qty"),
        ("ready", "Ready", "date"),
        ("on_time", "On time", "text"),
    ]
    rows = [{**ln, "on_time": "yes" if ln["on_time"] else "no", "uom": ""} for ln in lines]
    out = {**out, "summary": {"lines": len(lines), "on_time": len(lines) - len(late), "late": len(late)}}
    return ToolOutput(
        "order_fulfilment",
        "Order fulfilment",
        answer,
        [_table("Open order lines", cols, rows)],
        None,
        [{"code": "recommendation_only", "message": "Planning result; nothing is booked or changed."}],
        ["Which materials should we buy?", "Show the material plan"],
        out,
    )


def material_plan(ctx: ToolContext, a: ItemFilterArgs) -> ToolOutput:
    out = _svc(ctx).material_plan(ctx.principal, item_id=a.item_id)
    rows = out["planned_orders"]
    buy = [r for r in rows if r["action"] == "buy"]
    make = [r for r in rows if r["action"] == "make"]
    overdue = [r for r in rows if r["release"] and r["release"] < out["today"]]
    undated = [r for r in rows if r["release"] is None]
    answer = f"{len(rows)} planned orders: {len(buy)} to buy and {len(make)} to make."
    if overdue:
        first = overdue[0]
        answer += f" {len(overdue)} should already have been released, e.g. {first['action']} {first['quantity']} {first['item_id']} by {first['release']}."
    if undated:
        answer += f" {len(undated)} cannot be dated because a lead time or BOM is missing."
    cols = [
        ("item_id", "Item", "text"),
        ("warehouse_id", "Warehouse", "text"),
        ("action", "Make / buy", "text"),
        ("quantity", "Quantity", "qty"),
        ("release", "Release by", "date"),
        ("need", "Needed", "date"),
        ("ready", "Earliest ready", "date"),
        ("explanation", "Why", "text"),
    ]
    out = {
        **out,
        "summary": {
            "orders": len(rows),
            "buy": len(buy),
            "make": len(make),
            "overdue": len(overdue),
            "undated": len(undated),
        },
    }
    return ToolOutput(
        "material_plan",
        "Material plan",
        answer,
        [_table("Planned orders", cols, [{**r, "uom": ""} for r in rows])],
        None,
        [
            {
                "code": "recommendation_only",
                "message": "Planned orders are suggestions; no purchase or production order is created.",
            }
        ],
        ["Compare suppliers for the first item to buy"],
        out,
    )


def bom_explosion(ctx: ToolContext, a: BomArgs) -> ToolOutput:
    out = _svc(ctx).bom(ctx.principal, a.item_id, a.quantity)
    totals = out["totals"]
    blockers = _blockers(out["issues"])
    answer = (
        f"Making {out['quantity']} {a.item_id} needs {len(totals)} components: "
        + ", ".join(f"{v} {k}" for k, v in list(totals.items())[:6])
        + ("." if len(totals) <= 6 else ", …")
    )
    if blockers:
        answer += " " + blockers[0]
    rows = [{"component_id": k, "quantity": v, "uom": ""} for k, v in totals.items()]
    out = {**out, "summary": {"components": len(totals)}}
    return ToolOutput(
        "bom_explosion",
        "BOM explosion",
        answer,
        [
            _table(
                f"Components for {out['quantity']} {a.item_id}",
                [("component_id", "Component", "text"), ("quantity", "Quantity", "qty")],
                rows,
            )
        ],
        None,
        [],
        [],
        out,
    )


def supplier_comparison(ctx: ToolContext, a: SupplierArgs) -> ToolOutput:
    out = _svc(ctx).suppliers(ctx.principal, a.item_id, a.quantity, need_date=a.need_date, policy=a.policy)
    answer = out["recommendation"]
    if out["gaps"]:
        answer += " " + out["gaps"][0]
    excluded = [o for o in out["offers"] if not o["eligible"]]
    if excluded:
        answer += " Not eligible: " + "; ".join(f"{o['supplier_name']} ({o['reasons'][0]})" for o in excluded[:3]) + "."
    cols = [
        ("rank", "Rank", "int"),
        ("supplier_name", "Supplier", "text"),
        ("effective_unit_cost", "Cost per unit needed", "text"),
        ("currency", "Currency", "text"),
        ("earliest_delivery", "Earliest delivery", "date"),
        ("rejection_pct", "Rejected %", "text"),
        ("on_time_pct", "On time %", "text"),
        ("score", "Score", "text"),
        ("eligible", "Eligible", "text"),
    ]
    rows = [{**o, "eligible": "yes" if o["eligible"] else "no: " + "; ".join(o["reasons"])} for o in out["offers"]]
    return ToolOutput(
        "supplier_comparison",
        "Supplier comparison",
        answer,
        [_table(f"Offers for {a.item_id} ({a.policy})", cols, rows)],
        None,
        [{"code": "recommendation_only", "message": "No purchase order is created or approved."}],
        [],
        out,
    )


def duplicate_items(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    out = _svc(ctx).duplicates(ctx.principal)
    found = out["findings"]
    if not found:
        answer = "No probable or possible duplicate item records were found."
    else:
        f = found[0]
        answer = f"{len(found)} item pairs need review. {f['item_a']} and {f['item_b']}: {f['verdict'].replace('_', ' ')} ({'; '.join(f['reasons'])})."
    cols = [
        ("item_a", "Item", "text"),
        ("item_b", "Item", "text"),
        ("verdict", "Verdict", "text"),
        ("confidence", "Confidence", "text"),
        ("action", "Action", "text"),
    ]
    rows = [{**f, "reasons": "; ".join(f["reasons"])} for f in found]
    out = {**out, "summary": {"pairs": len(found)}}
    return ToolOutput(
        "duplicate_items",
        "Duplicate items",
        answer,
        [_table("Possible duplicates", cols, rows)],
        None,
        [{"code": "review_only", "message": "Nothing is merged, renamed or deleted."}],
        [],
        out,
    )


def lifecycle_review(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    out = _svc(ctx).lifecycle(ctx.principal)
    found = out["findings"]
    by: dict[str, list[dict[str, Any]]] = {}
    for f in found:
        by.setdefault(f["verdict"], []).append(f)
    parts = [f"{len(v)} {k.replace('_', ' ')}" for k, v in sorted(by.items())]
    answer = ("Lifecycle review: " + ", ".join(parts) + ".") if parts else "No lifecycle findings for items with stock."
    if by.get("critical_keep"):
        answer += f" {by['critical_keep'][0]['item_id']} is kept although it has not moved: it is marked critical."
    cols = [
        ("item_id", "Item", "text"),
        ("verdict", "Verdict", "text"),
        ("on_hand", "On hand", "qty"),
        ("action", "Action", "text"),
        ("evidence", "Evidence", "text"),
    ]
    rows = [{**f, "evidence": "; ".join(f["evidence"]), "uom": ""} for f in found]
    out = {**out, "summary": {k: len(v) for k, v in by.items()}}
    return ToolOutput(
        "lifecycle_review",
        "Lifecycle review",
        answer,
        [_table("Lifecycle findings", cols, rows)],
        None,
        [{"code": "review_only", "message": "An authorised user decides; nothing is disposed of."}],
        [],
        out,
    )


def planning_scope(ctx: ToolContext, a: ScopeArgs) -> ToolOutput:
    out = _svc(ctx).assess(ctx.principal, a.question)
    if out["capability_gaps"]:
        answer = "This cannot be calculated yet: " + " ".join(out["capability_gaps"])
    elif out["missing"]:
        answer = "Some of this can be answered, but data is missing: " + " ".join(out["questions"][:3])
    else:
        answer = "The data needed for this is available; ask about orders, materials, suppliers or BOMs directly."
    return ToolOutput("planning_scope", "What can be calculated", answer, [], None, [], out["questions"][:3], out)


def customer_commitment(ctx: ToolContext, a: CommitmentArgs) -> ToolOutput:
    svc = _svc(ctx)
    listing = svc.commitments(ctx.principal)
    at_risk = listing["at_risk"]
    by_value = sorted(at_risk, key=lambda r: Decimal(r["order_value"] or 0), reverse=True)  # most value at stake first
    key = None
    basis = ""
    note = ""
    if a.order_id:
        wanted = a.order_id.upper()
        key = next(
            (r["key"] for r in at_risk if r["key"].upper() == wanted or r["key"].upper().startswith(wanted + "/")), None
        )
        if key is None:
            known = svc.fulfilment(ctx.principal, order_id=wanted.split("/")[0])["lines"]
            known = [ln for ln in known if "/" not in wanted or ln["key"].upper() == wanted]
            note = (
                f"{a.order_id} is on time with the current plan; no premium sourcing is needed."
                if known
                else f"I couldn't find an open order {a.order_id} in your scope."
            )
    elif by_value:
        named = _pick_by_hint(by_value, a.hint)
        key = (named or by_value)[0]["key"]
        basis = "" if named else "the highest-value order at risk, "
    if key is None:
        answer = note or "Every open order line can be delivered on time; no premium sourcing is needed."
        out = {**listing, "summary": {"at_risk": len(at_risk)}}
        return ToolOutput(
            "customer_commitment",
            "Customer commitment protection",
            answer,
            [],
            None,
            [{"code": "recommendation_only", "message": "Nothing is ordered or approved."}],
            [],
            out,
        )
    out = svc.commitment(ctx.principal, key)
    opts = out["options"]
    rec = next((o for o in opts if o["recommended"]), None)
    exp = out["exposure"]
    if not out["at_risk"]:
        answer = f"{key} is on time with the current plan; no premium sourcing is needed."
    elif out["feasible"] and rec:
        answer = (
            f"{key} ({basis}{out['quantity']} {out['item_id']} for {out['customer_id']}, due {out['due']}) can still be "
            f"delivered on {out['recommended_delivery']} by sourcing from {rec['label']}."
        )
        if exp.get("order_value") is not None:
            answer += f" Order value at stake: {exp['order_value']} {exp['currency']}."
        if out["explanation"]:
            answer += " " + out["explanation"][0]
    else:
        answer = f"No eligible sourcing option delivers {key} ({basis}{out['item_id']} for {out['customer_id']}) by {out['due']}."
        if out["fallbacks"]:
            answer += " " + " ".join(out["fallbacks"][:2])
    cols = [
        ("label", "Option", "text"),
        ("material_id", "Material", "text"),
        ("material_arrival", "Material arrival", "date"),
        ("production_complete", "Production completion", "date"),
        ("customer_delivery", "Customer delivery", "date"),
        ("total_cost", "Total cost", "text"),
        ("incremental_cost", "vs cheapest eligible", "text"),
        ("feasible", "Feasible", "text"),
    ]
    rows = [
        {
            **o,
            "feasible": ("yes" if o["meets_deadline"] else "no")
            if o["eligible"]
            else "not eligible: " + "; ".join(o["reasons"]),
        }
        for o in opts
    ]
    others = [r["key"] for r in by_value if r["key"] != key]
    if others and not a.order_id:
        answer += f" {len(at_risk)} order lines are at risk in total; ask about any of them, e.g. {others[0]}."
    out = {
        **out,
        "at_risk_lines": at_risk,
        "summary": {
            "at_risk": len(at_risk),
            "options": len(opts),
            "eligible": sum(1 for o in opts if o["eligible"]),
            "meet_deadline": sum(1 for o in opts if o["eligible"] and o["meets_deadline"]),
        },
    }
    return ToolOutput(
        "customer_commitment",
        "Customer commitment protection",
        answer,
        [_table(f"Sourcing options for {key} (due {out['due']})", cols, rows)],
        None,
        [
            {
                "code": "approval_required",
                "message": "Recommendation only: a buyer approves; no purchase order is created.",
            }
        ],
        ["Compare suppliers for the critical material", "Which orders are at risk?"],
        out,
    )


PLANNING_TOOLS = (
    ToolDef(
        "order_fulfilment",
        "Whether open customer orders can be delivered on time, from stock, open POs, approved alternates or new make/buy, with the reason for each delay.",
        OrderArgs,
        (Permission.INVENTORY_READ,),
        order_fulfilment,
    ),
    ToolDef(
        "material_plan",
        "Time-phased material requirements: what to buy or make, how much, release and need dates, from BOMs, stock and open supply.",
        ItemFilterArgs,
        (Permission.INVENTORY_READ,),
        material_plan,
    ),
    ToolDef(
        "bom_explosion",
        "Every component needed to make a quantity of an item, multi-level, with scrap and yield.",
        BomArgs,
        (Permission.INVENTORY_READ,),
        bom_explosion,
    ),
    ToolDef(
        "supplier_comparison",
        "Compare approved suppliers for an item before a PO: cost per unit needed, MOQ, lead time vs need date, quality and delivery record, under a ranking policy (balanced, urgent, lowest_cost, quality_critical).",
        SupplierArgs,
        (Permission.INVENTORY_READ, Permission.COST_READ),
        supplier_comparison,
    ),
    ToolDef(
        "customer_commitment",
        "Customer Commitment Protection: for a late customer order (by id, or the customer or product named), which supplier or split meets the customer date across supplier, receiving, production and shipping, what it costs versus the cheapest eligible offer, and the order value and penalties at stake.",
        CommitmentArgs,
        (Permission.INVENTORY_READ, Permission.COST_READ),
        customer_commitment,
    ),
    ToolDef(
        "duplicate_items",
        "Item master records that may be duplicates, with the reasons; nothing is merged.",
        NoArgs,
        (Permission.INVENTORY_READ,),
        duplicate_items,
    ),
    ToolDef(
        "lifecycle_review",
        "Obsolescence review that never calls an item obsolete from inactivity alone (critical spares, BOM use, demand, superseded items).",
        NoArgs,
        (Permission.INVENTORY_READ,),
        lifecycle_review,
    ),
    ToolDef(
        "planning_scope",
        "For questions outside the built calculations (capacity, forecasting …): what can and cannot be calculated and what data is missing.",
        ScopeArgs,
        (Permission.INVENTORY_READ,),
        planning_scope,
    ),
)
