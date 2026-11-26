"""Stock ageing buckets (V4 visuals, docs/05-plan/PRODUCT_V3_PLAN.md §5.2): on-hand stock grouped by how long since its
item last left that warehouse (0–90, 91–180, 181–365, over 365 days, never issued). Counts item–warehouse pairs for
everyone; adds on-hand value per currency for roles with cost access. One statement, summed in the source, scoped.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement

from lumiant.analyses.cache import cached
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError, ForbiddenError
from lumiant.query.service import QueryService, meta_warnings

BUCKETS = (
    ("0-90", "0–90 days"),
    ("91-180", "91–180 days"),
    ("181-365", "181–365 days"),
    ("365+", "Over 365 days"),
    ("never", "Never issued"),
)
AGEING_RULE = (
    "Item–warehouse pairs with stock on hand, grouped by days from their last ISSUE movement to the data timestamp. "
    "Pairs with no issue in the available history are 'never issued'. Value is on-hand quantity × valuation price."
)


def run_ageing(query: QueryService, principal: Principal) -> dict[str, Any]:
    return cached(query, principal, "stock_ageing", (), lambda: _run(query, principal))


def _run(query: QueryService, principal: Principal) -> dict[str, Any]:
    mapping = query.mapping(principal.tenant_id)
    needs = {
        "stock_balance": ("item_id", "warehouse_id", "quantity"),
        "inventory_transaction": ("item_id", "warehouse_id", "txn_type", "posting_date"),
    }
    for ds, fields in needs.items():
        if not mapping.is_mapped(ds) or any(mapping.field(ds, f) is None for f in fields):
            raise AppError("analysis_unavailable", "Ageing needs stock and dated issue movements.", 409)
    if not principal.scope.all and not principal.scope.ids:
        raise ForbiddenError("forbidden_scope", "No warehouses are assigned to your account.")
    meta = query.tenant_meta(principal.tenant_id)
    as_of = meta.data_as_of.date() if meta.data_as_of else None
    if as_of is None:
        raise AppError("analysis_unavailable", "Ageing needs the data timestamp, which is unknown.", 409)
    cost = principal.has(Permission.COST_READ) and mapping.field("stock_balance", "valuation_price") is not None
    has_currency = mapping.field("stock_balance", "currency") is not None
    ids = sorted(principal.scope.ids)

    sb = mapping.table("stock_balance").alias("sb")
    tx = mapping.table("inventory_transaction").alias("tx")

    def s(n: str) -> ColumnElement[Any]:
        return mapping.column_expr("stock_balance", n, sb)

    def t(n: str) -> ColumnElement[Any]:
        return mapping.column_expr("inventory_transaction", n, tx)

    def scoped(col: ColumnElement[Any]) -> list[ColumnElement[Any]]:
        return [] if principal.scope.all else [col.in_(ids)]

    currency = s("currency") if (cost and has_currency) else sa.literal("", sa.String)
    onhand = (
        sa.select(
            s("item_id").label("item_id"),
            s("warehouse_id").label("warehouse_id"),
            currency.label("currency"),
            sa.func.sum(s("quantity")).label("qty"),
            *([sa.func.sum(s("stock_value")).label("value")] if cost else []),
        )
        .where(*scoped(s("warehouse_id")))
        .group_by(s("item_id"), s("warehouse_id"), *([currency] if cost and has_currency else []))
        .having(sa.func.sum(s("quantity")) > 0)
        .subquery("onhand")
    )
    last = (
        sa.select(
            t("item_id").label("item_id"),
            t("warehouse_id").label("warehouse_id"),
            sa.func.max(t("posting_date")).label("last_issue"),
        )
        .where(t("txn_type") == "ISSUE", *scoped(t("warehouse_id")))
        .group_by(t("item_id"), t("warehouse_id"))
        .subquery("last")
    )
    bucket = sa.case(
        (last.c.last_issue.is_(None), "never"),
        (last.c.last_issue >= as_of - timedelta(days=90), "0-90"),
        (last.c.last_issue >= as_of - timedelta(days=180), "91-180"),
        (last.c.last_issue >= as_of - timedelta(days=365), "181-365"),
        else_="365+",
    ).label("bucket")
    pairs = (
        sa.select(bucket, onhand.c.currency, *([onhand.c.value] if cost else []))
        .select_from(
            onhand.outerjoin(
                last, sa.and_(onhand.c.item_id == last.c.item_id, onhand.c.warehouse_id == last.c.warehouse_id)
            )
        )
        .subquery("pairs")
    )
    stmt = sa.select(
        pairs.c.bucket,
        pairs.c.currency,
        sa.func.count().label("pairs"),
        *([sa.func.sum(pairs.c.value).label("value")] if cost else []),
    ).group_by(pairs.c.bucket, pairs.c.currency)
    raw = query.execute_select(
        principal, stmt, action="analysis:stock_ageing", dataset="stock_balance", fetch_limit=100
    )
    found: dict[tuple[str, str], tuple[int, Any]] = {
        (str(r[0]), str(r[1] or "")): (int(r[2]), r[3] if cost else None) for r in raw.rows
    }
    currencies = sorted({c for _, c in found}) or [""]
    buckets = []
    for key, label in BUCKETS:
        row: dict[str, Any] = {
            "bucket": key,
            "label": label,
            "pairs": sum(n for (b, _), (n, _v) in found.items() if b == key),
        }
        if cost:
            row["value"] = {
                c: str(Decimal(found[(key, c)][1] or 0).quantize(Decimal("0.01"), ROUND_HALF_EVEN))
                for c in currencies
                if (key, c) in found
            }
        buckets.append(row)
    return {
        "as_of": as_of.isoformat(),
        "rule": AGEING_RULE,
        "buckets": buckets,
        "currencies": [c for c in currencies if c],
        "value_visible": cost,
        "warnings": [w.__dict__ for w in meta_warnings(meta)],
    }
