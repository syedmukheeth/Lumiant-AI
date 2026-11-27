"""`inventory_levers`: where money is tied up or at risk in stock, sized by the deterministic analyses (S11).

It answers business-goal questions ("how do we free up cash?", "what should I do to make more profit?") honestly.
Inventory data can show stock above its maximum, stock that has not moved, lots expired or about to expire, items
short of their reorder level, and gaps that hide value. It cannot show sales, selling prices or margins unless they
are mapped, and the tool says so instead of guessing.

Values come from one scoped query on `stock_balance` (sum of on-hand value per item and warehouse, cost access only)
and are attributed to each finding exactly, in Decimal, per currency. Levers overlap (a dormant item can also be in
excess), so they are never added together.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from lumiant.agent.tools import TOOLS, NoArgs, ToolContext, ToolDef, ToolOutput, _amount, _col
from lumiant.analyses.below_reorder import BelowReorderFilters, run_below_reorder
from lumiant.analyses.risks import run_data_quality, run_dormant, run_expiring
from lumiant.auth.permissions import Permission
from lumiant.core.errors import AppError
from lumiant.query.plan import QueryPlan

LEVER_ROWS = 200  # flagged pairs (or lots) valued per lever; more than this is said, never silently dropped
DORMANT_DAYS = 270
EXPIRY_DAYS = 90


@dataclass(frozen=True)
class _Pair:
    qty: Decimal
    uom: str
    value: Decimal
    currency: str


def _dec(value: Any) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _pair_values(ctx: ToolContext, item_ids: set[str]) -> tuple[dict[tuple[str, str], _Pair], bool]:
    """On-hand quantity and value per (item, warehouse) for the given items. Pairs held in more than one unit or
    currency are left out (they cannot be attributed exactly). Returns (pairs, complete)."""
    if not item_ids:
        return {}, True
    tenant = ctx.query.tenants.get(ctx.principal.tenant_id)
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "dimensions": ["item_id", "warehouse_id"],
            "measures": [
                {"field": "quantity", "agg": "sum", "alias": "qty"},
                {"field": "stock_value", "agg": "sum", "alias": "value"},
            ],
            "filters": [
                {"field": "item_id", "op": "in", "value": sorted(item_ids)[:500]},
                {"field": "quantity", "op": "gt", "value": "0"},
            ],
            "limit": tenant.policies.max_rows,
        }
    )
    res = ctx.query.run_plan(plan, ctx.principal, action="agent:inventory_levers")
    seen: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in res.payload()["data"]:
        seen[(str(row["item_id"]), str(row["warehouse_id"]))].append(row)
    pairs: dict[tuple[str, str], _Pair] = {}
    for key, rows in seen.items():
        if len(rows) != 1:
            continue
        r = rows[0]
        qty, value = _dec(r.get("qty")), _dec(r.get("value"))
        if qty is None or value is None or qty <= 0:
            continue
        pairs[key] = _Pair(qty, str(r.get("uom") or ""), value, str(r.get("currency") or ""))
    return pairs, not res.truncated and len(item_ids) <= 500


def _share(pair: _Pair | None, qty: Any, uom: Any) -> tuple[str, Decimal] | None:
    """The value of `qty` units of a pair, at the pair's own value per unit (same unit of measure only)."""
    q = _dec(qty)
    if pair is None or q is None or str(uom or "") != pair.uom:
        return None
    return pair.currency, pair.value * q / pair.qty


def _figure(totals: dict[str, Decimal]) -> str:
    return "; ".join(f"{cur} {_amount(v)}".strip() for cur, v in sorted(totals.items()) if v)


@dataclass
class _Lever:
    lever: str
    finding: str
    action: str
    totals: dict[str, Decimal]
    unvalued: int = 0
    available: bool = True

    def row(self) -> dict[str, Any]:
        finding = self.finding
        if self.unvalued:
            finding += f" ({self.unvalued} not valued: more than {LEVER_ROWS} rows, or several units or currencies)"
        return {"lever": self.lever, "finding": finding, "value": _figure(self.totals), "action": self.action}


def _value_rows(
    rows: list[dict[str, Any]], pairs: dict[tuple[str, str], _Pair] | None, qty_key: str, flagged: int
) -> tuple[dict[str, Decimal], int]:
    totals: dict[str, Decimal] = defaultdict(Decimal)
    valued = 0
    if pairs is not None:
        for r in rows:
            got = _share(pairs.get((str(r["item_id"]), str(r["warehouse_id"]))), r.get(qty_key), r.get("uom"))
            if got is not None:
                totals[got[0]] += got[1]
                valued += 1
    return dict(totals), (max(flagged - valued, 0) if pairs is not None else 0)


def _missing(ctx: ToolContext) -> list[str]:
    mapping = ctx.query.mapping(ctx.principal.tenant_id)
    notes = []
    if mapping.is_mapped("customer_order_line") and mapping.field("customer_order_line", "margin_pct") is not None:
        notes.append(
            "Only open customer orders carry selling prices and margins; there is no sales history, so profit for a "
            "future month cannot be calculated."
        )
    else:
        notes.append(
            "No sales history, selling prices or margins are in this organisation's data, so profit cannot be "
            "calculated. These figures show money tied up in stock and risks to supply, which are the inventory "
            "side of profit."
        )
    return notes


def inventory_levers(ctx: ToolContext, a: NoArgs) -> ToolOutput:
    can_cost = ctx.principal.has(Permission.COST_READ)
    levers: list[_Lever] = []
    warnings: list[dict[str, str]] = []
    provenance: dict[str, Any] | None = None

    def unavailable(lever: str, exc: AppError) -> _Lever:
        return _Lever(lever, f"Not available: {exc.message}", "", {}, available=False)

    excess = dormant = expiring = None
    try:
        excess = run_below_reorder(
            ctx.query, ctx.principal, BelowReorderFilters(), limit=LEVER_ROWS, offset=0, mode="excess"
        )
        provenance = excess.payload()["provenance"]
    except AppError as exc:
        levers.append(unavailable("Stock above maximum", exc))
    try:
        dormant = run_dormant(ctx.query, ctx.principal, days=DORMANT_DAYS, limit=LEVER_ROWS, offset=0)
    except AppError as exc:
        levers.append(unavailable(f"No issue in {DORMANT_DAYS} days", exc))
    try:
        expiring = run_expiring(ctx.query, ctx.principal, days=EXPIRY_DAYS, limit=LEVER_ROWS)
    except AppError as exc:
        levers.append(unavailable("Expired or expiring lots", exc))

    ids: set[str] = set()
    for res in (excess, dormant, expiring):
        if res is not None:
            ids |= {str(r["item_id"]) for r in res.payload()["data"]}
    pairs: dict[tuple[str, str], _Pair] | None = None
    if can_cost:
        pairs, complete = _pair_values(ctx, ids)
        if not complete:
            warnings.append(
                {
                    "code": "levers_partial",
                    "message": "Some stock could not be valued in one pass; figures are a floor.",
                }
            )

    if excess is not None:
        rows, n = excess.payload()["data"], int((excess.summary or {}).get("flagged", 0))
        totals, unvalued = _value_rows(rows, pairs, "excess", n)
        levers.append(
            _Lever(
                "Stock above maximum",
                f"Item–warehouse pairs above their maximum stock policy: {n}",
                "Stop or delay purchases for these items, move stock to sites that need it, or sell the surplus.",
                totals,
                unvalued,
            )
        )
    if dormant is not None:
        rows, n = dormant.payload()["data"], int((dormant.summary or {}).get("flagged", 0))
        totals, unvalued = _value_rows(rows, pairs, "on_hand", n)
        levers.append(
            _Lever(
                f"No issue in {DORMANT_DAYS} days",
                f"Item–warehouse pairs with stock not issued in {DORMANT_DAYS} days: {n}",
                "Review for return to supplier, transfer, sale or write-off; stop replenishing them.",
                totals,
                unvalued,
            )
        )
    if expiring is not None:
        rows = expiring.payload()["data"]
        s = expiring.summary or {}
        for status, label, count_key, action in (
            (
                "expired",
                "Expired lots",
                "expired_lots",
                "Quarantine and dispose of or claim them; check why they expired.",
            ),
            (
                "expiring",
                f"Lots expiring within {EXPIRY_DAYS} days",
                "expiring_lots",
                "Use these first (first-expiry-first-out), or sell or transfer them before they expire.",
            ),
        ):
            mine = [r for r in rows if r.get("status") == status]
            n = int(s.get(count_key, 0))
            totals, unvalued = _value_rows(mine, pairs, "quantity", len(mine))
            if n > len(mine) and pairs is not None:
                unvalued += n - len(mine)
            levers.append(_Lever(label, f"{label} on hand: {n}", action, totals, unvalued))
    try:
        below = run_below_reorder(ctx.query, ctx.principal, BelowReorderFilters(), limit=1, offset=0)
        n = int((below.summary or {}).get("flagged", 0))
        no_policy = int((below.summary or {}).get("pairs_without_policy", 0))
        levers.append(
            _Lever(
                "Below reorder level",
                f"Item–warehouse pairs below their reorder level: {n}",
                "Replenish these first: shortages stop production and lose sales, which costs more than stock.",
                {},
            )
        )
        if no_policy:
            levers.append(
                _Lever(
                    "No min/max policy",
                    f"Stocked item–warehouse pairs without a reorder policy: {no_policy}",
                    "Set minimum and maximum levels so excess and shortages can be detected.",
                    {},
                )
            )
    except AppError as exc:
        levers.append(unavailable("Below reorder level", exc))
    try:
        dq = run_data_quality(ctx.query, ctx.principal)
        gaps = {c["id"]: c for c in dq["checks"] if c.get("status") == "issue"}
        lines = sum(
            int(gaps[k]["count"] or 0) for k in ("missing_valuation_price", "zero_valuation_price") if k in gaps
        )
        if lines:
            levers.append(
                _Lever(
                    "Stock without a valuation price",
                    f"Stock lines with no or a zero valuation price: {lines}",
                    "Fix these prices: the value of this stock is missing from every figure above.",
                    {},
                )
            )
    except AppError:
        pass  # a failed check is not a lever; the other findings stand

    rows = [lv.row() for lv in levers]
    sized = [lv for lv in levers if lv.available and lv.totals]
    missing = _missing(ctx)
    if sized:
        lead = "; ".join(f"{lv.lever.lower()}: {_figure(lv.totals)}" for lv in sized[:3])
        answer = f"Money tied up in stock that could be freed — {lead}."
    else:
        counted = [lv for lv in levers if lv.available][:3]
        answer = (
            "What the inventory data shows: " + "; ".join(lv.finding for lv in counted) + "."
            if counted
            else ("None of the inventory levers can be checked with the data available.")
        )
        if not can_cost:
            answer += " Your role cannot view values, so the money involved is not shown."
    answer += " " + missing[0]
    if any(lv.unvalued for lv in levers):
        answer += " Some flagged stock could not be valued, so the figures are a floor."
    columns = [_col("lever", "Lever"), _col("finding", "Finding"), _col("action", "What to do")]
    if can_cost:
        columns.insert(2, _col("value", "Value at stake"))
    block = {"type": "table", "title": "Inventory levers", "columns": columns, "rows": rows}
    data = {
        "levers": rows,
        "missing": missing,
        "dormant_days": DORMANT_DAYS,
        "expiry_days": EXPIRY_DAYS,
        "valued_rows_per_lever": LEVER_ROWS,
        "totals": {lv.lever: {c: _amount(v) for c, v in lv.totals.items()} for lv in levers},
    }
    return ToolOutput(
        "inventory_levers",
        "Inventory levers",
        answer,
        [block],
        provenance,
        warnings,
        [
            "Which items are in excess?",
            f"Which items have not moved in {DORMANT_DAYS} days?",
            "Which lots are nearing expiry?",
        ],
        data,
    )


LEVER_TOOLS = (
    ToolDef(
        "inventory_levers",
        "For business goals (profit, cash, working capital, cost reduction, 'what should I do'): sizes the inventory "
        "levers the data can see - stock above maximum, stock not issued in 270 days, expired and soon-expiring lots, "
        "items below reorder level, stock without a valuation price - with the value at stake per currency (cost "
        "access) and a recommended action each, and says what the data cannot show (sales, selling prices, margins).",
        NoArgs,
        (Permission.INVENTORY_READ,),
        inventory_levers,
    ),
)
TOOLS.update({t.name: t for t in LEVER_TOOLS})
