"""Inventory value over time (V4 command centre, docs/05-plan/PRODUCT_V3_PLAN.md §5.1).

Month-end stock is rebuilt from movements, which are signed (receipts positive, issues negative): quantity at a month
end = quantity on hand now − the movements posted after that month end, per item and warehouse. It is valued at the
**current** valuation price of that item and warehouse, so the trend shows how much stock moved, not how prices
changed; the rule says so. Receipts and issues per month are valued at each movement's own unit cost.

Everything is summed in the source (window-free CASE sums, one statement per figure set), Decimal end to end, with the
caller's warehouse scope.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement

from lumiant.analyses.cache import cached
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError, ForbiddenError
from lumiant.query.service import QueryService, meta_warnings

VALUE_TREND_RULE = (
    "Month-end stock = stock on hand now minus the movements posted after that month end, per item and warehouse, "
    "valued at today's valuation price (so the line shows stock moving, not prices changing). Receipts and issues are "
    "valued at each movement's unit cost. Stock lines without a valuation price are left out."
)


def month_ends(as_of: date, months: int) -> list[date]:
    """The last `months` month ends before `as_of`, oldest first, then `as_of` itself (the current point)."""
    ends: list[date] = []
    y, m = as_of.year, as_of.month
    for _ in range(months):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        ends.append(date(y, m, calendar.monthrange(y, m)[1]))
    return [*reversed(ends), as_of]


def run_value_trend(query: QueryService, principal: Principal, *, months: int) -> dict[str, Any]:
    if not principal.has(Permission.COST_READ):
        raise ForbiddenError("forbidden_field", "Your role cannot view cost or value information.")
    return cached(query, principal, "value_trend", (months,), lambda: _run(query, principal, months))


def _run(query: QueryService, principal: Principal, months: int) -> dict[str, Any]:
    mapping = query.mapping(principal.tenant_id)
    needs = {
        "stock_balance": ("item_id", "warehouse_id", "quantity", "valuation_price"),
        "inventory_transaction": ("item_id", "warehouse_id", "quantity", "posting_date"),
    }
    for ds, fields in needs.items():
        if not mapping.is_mapped(ds) or any(mapping.field(ds, f) is None for f in fields):
            raise AppError("analysis_unavailable", "A value trend needs stock with prices and dated movements.", 409)
    if not principal.scope.all and not principal.scope.ids:
        raise ForbiddenError("forbidden_scope", "No warehouses are assigned to your account.")
    meta = query.tenant_meta(principal.tenant_id)
    as_of = meta.data_as_of.date() if meta.data_as_of else date.today()
    ends = month_ends(as_of, months)
    scope_ids = sorted(principal.scope.ids)
    has_currency = mapping.field("stock_balance", "currency") is not None
    has_cost = mapping.field("inventory_transaction", "unit_cost") is not None

    sb = mapping.table("stock_balance").alias("sb")
    tx = mapping.table("inventory_transaction").alias("tx")

    def s(name: str) -> ColumnElement[Any]:
        return mapping.column_expr("stock_balance", name, sb)

    def t(name: str) -> ColumnElement[Any]:
        return mapping.column_expr("inventory_transaction", name, tx)

    def scoped(col: ColumnElement[Any]) -> list[ColumnElement[Any]]:
        return [] if principal.scope.all else [col.in_(scope_ids)]

    currency = s("currency") if has_currency else sa.literal(None, sa.String)
    onhand = (
        sa.select(
            s("item_id").label("item_id"),
            s("warehouse_id").label("warehouse_id"),
            currency.label("currency"),
            sa.func.sum(s("quantity")).label("qty"),
            sa.func.max(s("valuation_price")).label("price"),
        )
        .where(s("valuation_price").is_not(None), *scoped(s("warehouse_id")))
        .group_by(s("item_id"), s("warehouse_id"), *([currency] if has_currency else []))
        .subquery("onhand")
    )
    after = (
        sa.select(
            t("item_id").label("item_id"),
            t("warehouse_id").label("warehouse_id"),
            *(
                sa.func.sum(sa.case((t("posting_date") > end, t("quantity")), else_=0)).label(f"a{k}")
                for k, end in enumerate(ends)
            ),
        )
        .where(*scoped(t("warehouse_id")))
        .group_by(t("item_id"), t("warehouse_id"))
        .subquery("after")
    )
    joined = onhand.outerjoin(
        after, sa.and_(onhand.c.item_id == after.c.item_id, onhand.c.warehouse_id == after.c.warehouse_id)
    )
    values_stmt = (
        sa.select(
            onhand.c.currency,
            *(
                sa.func.sum((onhand.c.qty - sa.func.coalesce(after.c[f"a{k}"], 0)) * onhand.c.price).label(f"v{k}")
                for k in range(len(ends))
            ),
        )
        .select_from(joined)
        .group_by(onhand.c.currency)
    )
    values = query.execute_select(
        principal, values_stmt, action="analysis:value_trend", dataset="stock_balance", fetch_limit=20
    )

    flows: dict[str | None, list[tuple[Any, Any]]] = {}
    if has_cost:
        tx_currency = (
            t("currency")
            if mapping.field("inventory_transaction", "currency") is not None
            else sa.literal(None, sa.String)
        )
        value = t("quantity") * t("unit_cost")
        cols = []
        for k in range(1, len(ends)):
            window = sa.and_(t("posting_date") > ends[k - 1], t("posting_date") <= ends[k])
            cols.append(sa.func.sum(sa.case((sa.and_(window, t("quantity") > 0), value), else_=0)).label(f"r{k}"))
            cols.append(sa.func.sum(sa.case((sa.and_(window, t("quantity") < 0), -value), else_=0)).label(f"i{k}"))
        flow_stmt = (
            sa.select(tx_currency.label("currency"), *cols)
            .where(t("unit_cost").is_not(None), t("posting_date") > ends[0], *scoped(t("warehouse_id")))
            .group_by(tx_currency)
        )
        raw = query.execute_select(
            principal,
            flow_stmt,
            action="analysis:value_trend",
            dataset="inventory_transaction",
            fetch_limit=20,
            audit=False,
        )
        for row in raw.rows:
            flows[row[0]] = [(row[1 + 2 * (k - 1)], row[2 + 2 * (k - 1)]) for k in range(1, len(ends))]

    series = []
    for row in values.rows:
        cur = row[0]
        points = []
        for k, end in enumerate(ends):
            receipts, issues = (flows.get(cur) or [])[k - 1] if k > 0 and flows.get(cur) else (None, None)
            points.append(
                {
                    "period": end.strftime("%Y-%m") if k < len(ends) - 1 else "now",
                    "date": end.isoformat(),
                    "value": _str(row[1 + k]),
                    "receipts_value": _str(receipts),
                    "issues_value": _str(issues),
                }
            )
        series.append({"currency": cur, "points": points})
    query.record(principal, "analysis:value_trend", "stock_balance", "allow", "ok", rows=len(series))
    return {
        "as_of": as_of.isoformat(),
        "months": months,
        "rule": VALUE_TREND_RULE,
        "series": series,
        "warehouses": "all" if principal.scope.all else scope_ids,
        "warnings": [w.__dict__ for w in meta_warnings(meta)],
    }


def _str(value: Any) -> str | None:
    """Exact decimal text, 2 places for money; no float ever."""
    if value is None:
        return None
    from decimal import ROUND_HALF_EVEN, Decimal

    return str(Decimal(value).quantize(Decimal("0.01"), ROUND_HALF_EVEN))
