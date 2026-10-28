"""Value concentration (Pareto): how few items hold most of the on-hand value, per currency.

Two governed queries: per-currency totals over every stocked item, then the highest-value items (capped at the
tenant's row limit) for the cumulative curve. If the cap is reached before the target share, the result says so
instead of extrapolating. Shares are exact Decimal arithmetic on the query results, rounded only for display.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError
from lumiant.query.plan import QueryPlan
from lumiant.query.service import QueryService

ID = "concentration"
PCT = Decimal("0.1")


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    return (part * 100 / whole).quantize(PCT, rounding=ROUND_HALF_EVEN) if whole else Decimal(0)


def run_concentration(
    query: QueryService,
    principal: Principal,
    *,
    filters: list[dict[str, Any]] | None = None,
    target_pct: int = 80,
    top_rows: int = 15,
) -> dict[str, Any]:
    if not principal.has(Permission.COST_READ):
        raise AppError("forbidden_field", "Your role cannot view inventory values.", 403)
    base = [*(filters or []), {"field": "quantity", "op": "gt", "value": "0"}]
    totals = query.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "stock_balance",
                "measures": [
                    {"field": "stock_value", "agg": "sum", "alias": "total"},
                    {"field": "item_id", "agg": "count_distinct", "alias": "items"},
                ],
                "filters": base,
            }
        ),
        principal,
        action=f"analysis:{ID}",
    )
    cap = query.tenants.get(principal.tenant_id).policies.max_rows
    ranked = query.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "stock_balance",
                "dimensions": ["item_id", "item.item_code", "item.description"],
                "measures": [{"field": "stock_value", "agg": "sum", "alias": "value"}],
                "filters": base,
                "order_by": [{"field": "value", "direction": "desc"}],
                "limit": cap,
            }
        ),
        principal,
        action=f"analysis:{ID}",
    )
    target = Decimal(target_pct)
    currencies: list[dict[str, Any]] = []
    top: list[dict[str, Any]] = []
    for t in totals.rows:
        cur, total, items = t.get("currency"), Decimal(t["total"] or 0), int(t["items"] or 0)
        if cur is None or total <= 0:
            continue  # unpriced stock has no value to concentrate; data quality reports it
        rows = [r for r in ranked.rows if r.get("currency") == cur and r["value"] is not None]
        cum, needed = Decimal(0), None
        for i, r in enumerate(rows):
            cum += Decimal(r["value"])
            if needed is None and cum * 100 >= total * target:
                needed = i + 1
            if i < top_rows:
                top.append(
                    {
                        "item_id": r["item_id"],
                        "item_code": r["item.item_code"],
                        "description": r["item.description"],
                        "currency": cur,
                        "value": r["value"],
                        "share_pct": _pct(Decimal(r["value"]), total),
                        "cumulative_pct": _pct(cum, total),
                    }
                )
        top10 = sum((Decimal(r["value"]) for r in rows[:10]), Decimal(0))
        currencies.append(
            {
                "currency": cur,
                "total": total,
                "stocked_items": items,
                "target_pct": target_pct,
                "items_for_target": needed,
                "items_for_target_pct": _pct(Decimal(needed), Decimal(items)) if needed and items else None,
                "top10_share_pct": _pct(top10, total),
                "complete": needed is not None,
                "ranked_rows": len(rows),
            }
        )
    currencies.sort(key=lambda c: c["total"], reverse=True)
    warnings = [w.__dict__ for w in (*totals.warnings, *ranked.warnings) if w.code not in ("auto_grouped", "truncated")]
    return {
        "currencies": currencies,
        "top": top,
        "row_cap": cap,
        "provenance": ranked.provenance,
        "warnings": warnings,
    }
