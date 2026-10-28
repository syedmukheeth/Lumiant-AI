"""M2 analyses. Every one runs through QueryService (validation, scope, guard, audit) and every definition
is a DRAFT until the customer approves it (docs/04-domain/INVENTORY_CALCULATIONS.md)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement

from lumiant.analyses.below_reorder import BelowReorderFilters, run_below_reorder
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError, ForbiddenError
from lumiant.costing.abc import AbcConfig, classify
from lumiant.costing.engine import (
    CostingError,
    Movement,
    PurchaseLine,
    fifo_layers,
    latest_receipt_cost,
    latest_valid_purchase_price,
    moving_weighted_average,
    present,
)
from lumiant.costing.item_code import parse_item_code
from lumiant.mapping.resolver import UNMAPPED
from lumiant.query.compiler import ExactDecimal
from lumiant.query.plan import QueryPlan
from lumiant.query.results import Column, QueryResult, to_json_value
from lumiant.query.service import MetricRef, QueryService, meta_warnings

DORMANT_RULE = (
    "Item–warehouse pairs with positive on-hand stock and no ISSUE movement within the given number of days "
    "before the data timestamp (or no issue at all in the available history)."
)
EXPIRY_RULE = (
    "Stock lines with positive quantity in a lot whose expiry date is on or before the data timestamp plus the "
    "given number of days. Already-expired lots are included and marked."
)
ABC_RULE = (
    "Draft: items ranked by on-hand value in one currency; class A until the cumulative share before the item "
    "reaches the A cutoff, B until the B cutoff, otherwise C. Cutoffs are supplied by the caller (no defaults). "
    "Compared with the ABC class assigned in the source."
)
COST_RULES = {
    "moving_weighted_average": "Each receipt re-averages; issues leave the average; returns and adjustments at the current average.",
    "fifo": "Receipts form layers; issues consume the oldest layer first; value is the sum of remaining layers.",
    "latest_valid_purchase_price": "Most recent purchase line by order date whose status is in the tenant's valid list.",
    "latest_receipt_cost": "Unit cost of the most recent RECEIPT movement.",
    "source_valuation": "Source valuation value ÷ quantity from the stock balance, as provided by the source system.",
}
RECONCILE_TOLERANCE = Decimal("0.0002")  # source prices carry 4 decimals; below this is rounding noise


def _as_of(query: QueryService, tenant_id: str) -> date:
    meta = query.tenant_meta(tenant_id)
    return (meta.data_as_of or datetime.now(UTC)).date()


def _dec(value: Any) -> Decimal | None:
    return value if isinstance(value, Decimal) else None


def _money(value: Decimal | None, places: int = 4) -> str | None:
    return None if value is None else format(present(value, places), "f")


# --------------------------------------------------------------------------------------- dormant stock
def run_dormant(query: QueryService, principal: Principal, *, days: int, limit: int, offset: int) -> QueryResult:
    mapping = query.mapping(principal.tenant_id)
    action = "analysis:dormant_stock"
    needs = {
        "stock_balance": ("item_id", "warehouse_id", "quantity", "uom"),
        "inventory_transaction": ("item_id", "warehouse_id", "txn_type", "posting_date"),
    }
    for ds, fields in needs.items():
        if not mapping.is_mapped(ds) or any(mapping.field(ds, f) is None for f in fields):
            raise AppError(
                "analysis_unavailable",
                "This analysis needs stock balances and issue movements with posting dates, which are not all mapped.",
                409,
            )
    if not principal.scope.all and not principal.scope.ids:
        raise ForbiddenError("forbidden_scope", "No warehouses are assigned to your account.")
    as_of = _as_of(query, principal.tenant_id)
    cutoff = as_of - timedelta(days=days)
    scope_ids = sorted(principal.scope.ids)

    def c(ds: str, name: str, table: Any) -> ColumnElement[Any]:
        return mapping.column_expr(ds, name, table)

    def scoped(col: ColumnElement[Any]) -> list[ColumnElement[Any]]:
        return [] if principal.scope.all else [col.in_(scope_ids)]

    sb = mapping.table("stock_balance").alias("sb")
    tx = mapping.table("inventory_transaction").alias("tx")
    it = mapping.table("item").alias("it") if mapping.is_mapped("item") else None
    onhand = (
        sa.select(
            c("stock_balance", "item_id", sb).label("item_id"),
            c("stock_balance", "warehouse_id", sb).label("warehouse_id"),
            c("stock_balance", "uom", sb).label("uom"),
            sa.func.sum(c("stock_balance", "quantity", sb)).label("on_hand"),
        )
        .where(*scoped(c("stock_balance", "warehouse_id", sb)))
        .group_by(
            c("stock_balance", "item_id", sb), c("stock_balance", "warehouse_id", sb), c("stock_balance", "uom", sb)
        )
        .having(sa.func.sum(c("stock_balance", "quantity", sb)) > 0)
        .cte("onhand")
    )
    issues = (
        sa.select(
            c("inventory_transaction", "item_id", tx).label("item_id"),
            c("inventory_transaction", "warehouse_id", tx).label("warehouse_id"),
            sa.func.max(c("inventory_transaction", "posting_date", tx)).label("last_issue"),
        )
        .where(
            c("inventory_transaction", "txn_type", tx) == "ISSUE",
            *scoped(c("inventory_transaction", "warehouse_id", tx)),
        )
        .group_by(c("inventory_transaction", "item_id", tx), c("inventory_transaction", "warehouse_id", tx))
        .cte("issues")
    )
    joined = onhand.outerjoin(
        issues, sa.and_(issues.c.item_id == onhand.c.item_id, issues.c.warehouse_id == onhand.c.warehouse_id)
    )
    if it is not None and mapping.field("item", "item_id") is not None:
        joined = joined.outerjoin(it, c("item", "item_id", it) == onhand.c.item_id)

    def opt(name: str, label: str) -> ColumnElement[Any]:
        if it is not None and mapping.field("item", name) is not None:
            return c("item", name, it).label(label)
        return sa.null().label(label)

    cond = sa.or_(issues.c.last_issue.is_(None), issues.c.last_issue < cutoff)
    base = (
        sa.select(
            onhand.c.item_id,
            opt("item_code", "item_code"),
            opt("description", "description"),
            opt("item_group", "item_group"),
            onhand.c.warehouse_id,
            onhand.c.uom,
            sa.type_coerce(onhand.c.on_hand, ExactDecimal()).label("on_hand"),
            issues.c.last_issue.label("last_issue"),
        )
        .select_from(joined)
        .where(cond)
    )
    stmt = (
        base.order_by(issues.c.last_issue.asc().nulls_first(), onhand.c.item_id, onhand.c.warehouse_id)
        .limit(limit + 1)
        .offset(offset)
    )
    count_stmt = sa.select(sa.func.count().label("total")).select_from(base.subquery("q"))
    raw = query.execute_select(principal, stmt, action=action, dataset="inventory_transaction", fetch_limit=limit + 1)
    total = int(
        query.execute_select(
            principal, count_stmt, action=action, dataset="inventory_transaction", fetch_limit=1, audit=False
        ).rows[0][0]
    )
    truncated = len(raw.rows) > limit
    rows = [dict(zip(raw.columns, r, strict=True)) for r in raw.rows[:limit]]
    for row in rows:
        last = row["last_issue"]
        row["days_since_issue"] = (as_of - last).days if isinstance(last, date) else None
    meta = query.tenant_meta(principal.tenant_id)
    provenance = query.provenance(
        principal,
        mapping,
        meta,
        dataset="inventory_transaction",
        source_datasets=["stock_balance", "inventory_transaction"],
        fields={
            "on_hand": f"SUM({mapping.physical_ref('stock_balance', 'quantity')})",
            "last_issue": f"MAX({mapping.physical_ref('inventory_transaction', 'posting_date')}) where "
            f"{mapping.physical_ref('inventory_transaction', 'txn_type')} = 'ISSUE'",
        },
        filters=[],
        auto_grouped=[],
        metric=MetricRef("dormant_stock", 1, "draft", DORMANT_RULE),
        row_count=len(rows),
        truncated=truncated,
        duration_ms=raw.duration_ms,
        stmt=stmt,
        rule=DORMANT_RULE,
    )
    provenance["parameters"] = {"days": days, "cutoff": cutoff.isoformat(), "as_of": as_of.isoformat()}
    query.record(principal, action, "inventory_transaction", "allow", "ok", rows=len(rows), ms=raw.duration_ms)
    cols = [
        Column(n, t, "dimension" if t == "string" else "measure")
        for n, t in (
            ("item_id", "string"),
            ("item_code", "string"),
            ("description", "string"),
            ("item_group", "string"),
            ("warehouse_id", "string"),
            ("uom", "string"),
            ("on_hand", "decimal"),
            ("last_issue", "date"),
            ("days_since_issue", "integer"),
        )
    ]
    return QueryResult(
        cols,
        rows,
        provenance,
        meta_warnings(meta),
        truncated,
        page={"offset": offset, "limit": limit, "total": total},
        summary={"flagged": total, "days": days, "cutoff": cutoff, "as_of": as_of},
    )


# --------------------------------------------------------------------------------------- expiring lots
def run_expiring(query: QueryService, principal: Principal, *, days: int, limit: int) -> QueryResult:
    mapping = query.mapping(principal.tenant_id)
    if mapping.field("lot", "expiry_date") is None or mapping.field("stock_balance", "lot_id") is None:
        raise AppError(
            "analysis_unavailable", "This analysis needs lot expiry dates, which are not mapped for this tenant.", 409
        )
    as_of = _as_of(query, principal.tenant_id)
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "dimensions": [
                "item_id",
                "item.item_code",
                "item.description",
                "warehouse_id",
                "lot_id",
                "lot.expiry_date",
                "quantity",
            ],
            "filters": [
                {"field": "quantity", "op": "gt", "value": "0"},
                {"field": "lot.expiry_date", "op": "lte", "value": (as_of + timedelta(days=days)).isoformat()},
            ],
            "order_by": [{"field": "lot.expiry_date", "direction": "asc"}],
            "limit": limit,
        }
    )
    result = query.run_plan(
        plan, principal, action="analysis:expiring_lots", metric=MetricRef("expiring_lots", 1, "draft", EXPIRY_RULE)
    )
    expired = 0
    for row in result.rows:
        expiry = row.get("lot.expiry_date")
        if isinstance(expiry, date):
            left = (expiry - as_of).days
            row["days_to_expiry"] = left
            row["status"] = "expired" if left < 0 else "expiring"
            expired += left < 0
    result.columns += [Column("days_to_expiry", "integer", "measure"), Column("status", "string", "dimension")]
    result.provenance["rule"] = EXPIRY_RULE
    result.provenance["parameters"] = {"days": days, "as_of": as_of.isoformat()}
    result.summary = {"expired": expired, "expiring": len(result.rows) - expired, "days": days}
    return result


# --------------------------------------------------------------------------------------- data quality
def _count_plan(dataset: str, filters: list[dict[str, Any]]) -> QueryPlan:
    return QueryPlan.model_validate(
        {"dataset": dataset, "measures": [{"field": "item_id", "agg": "count", "alias": "n"}], "filters": filters}
    )


def run_data_quality(query: QueryService, principal: Principal) -> dict[str, Any]:
    mapping = query.mapping(principal.tenant_id)
    checks: list[dict[str, Any]] = []

    def count(dataset: str, filters: list[dict[str, Any]], action: str) -> int:
        res = query.run_plan(_count_plan(dataset, filters), principal, action=action)
        return int(res.rows[0]["n"])

    total_items = count("item", [], "analysis:data_quality")
    for field, title in (
        ("description", "Items without a description"),
        ("item_group", "Items without an item group"),
        ("abc_class", "Items without an ABC class"),
        ("base_uom", "Items without a base unit of measure"),
        ("inventory_stage", "Items without an inventory stage"),
    ):
        if mapping.field("item", field) is None:
            checks.append({"id": f"missing_{field}", "title": title, "status": "not_mapped", "count": None})
            continue
        n = count("item", [{"field": field, "op": "is_null"}], "analysis:data_quality")
        checks.append({"id": f"missing_{field}", "title": title, "status": "ok" if n == 0 else "issue", "count": n})

    if principal.has(Permission.COST_READ) and mapping.field("stock_balance", "valuation_price") is not None:
        n = count(
            "stock_balance",
            [{"field": "valuation_price", "op": "is_null"}, {"field": "quantity", "op": "gt", "value": "0"}],
            "analysis:data_quality",
        )
        checks.append(
            {
                "id": "missing_valuation_price",
                "title": "Stock lines without a valuation price",
                "status": "ok" if n == 0 else "issue",
                "count": n,
            }
        )
    else:
        checks.append(
            {
                "id": "missing_valuation_price",
                "title": "Stock lines without a valuation price",
                "status": "restricted",
                "count": None,
            }
        )

    try:
        summary = run_below_reorder(query, principal, BelowReorderFilters(), limit=1, offset=0).summary or {}
        n = int(summary.get("pairs_without_policy", 0))
        checks.append(
            {
                "id": "pairs_without_policy",
                "title": "Stocked item–warehouse pairs without a reorder policy",
                "status": "ok" if n == 0 else "issue",
                "count": n,
            }
        )
    except AppError:
        checks.append(
            {
                "id": "pairs_without_policy",
                "title": "Stocked item–warehouse pairs without a reorder policy",
                "status": "not_mapped",
                "count": None,
            }
        )

    coding = query.tenants.get(principal.tenant_id).item_coding
    if coding is None:
        checks.append(
            {
                "id": "invalid_item_codes",
                "title": "Item codes that break the tenant coding rules",
                "status": "no_rules",
                "count": None,
            }
        )
    else:
        listing = query.run_plan(
            QueryPlan.model_validate({"dataset": "item", "dimensions": ["item_id", "item_code"], "limit": 1000}),
            principal,
            action="analysis:data_quality",
        )
        bad = [(r["item_id"], r["item_code"], parse_item_code(r["item_code"], coding).problems) for r in listing.rows]
        bad = [(i, c, p) for i, c, p in bad if p]
        checks.append(
            {
                "id": "invalid_item_codes",
                "title": "Item codes that break the tenant coding rules",
                "status": "ok" if not bad else "issue",
                "count": len(bad),
                "examples": [{"item_id": i, "item_code": c, "problems": list(p)} for i, c, p in bad[:10]],
                "checked": len(listing.rows),
                "partial": listing.truncated,
            }
        )
    checks += _source_checks(query, principal)
    meta = query.tenant_meta(principal.tenant_id)
    return {
        "checks": checks,
        "total_items": total_items,
        "warnings": [w.__dict__ for w in meta_warnings(meta)],
        "synthetic": meta.synthetic,
        "data_as_of": meta.data_as_of.isoformat() if meta.data_as_of else None,
    }


def _share(n: int, total: int) -> str | None:
    return None if total == 0 else format((Decimal(n) * 100 / Decimal(total)).quantize(Decimal("0.1")), "f")


def _source_checks(query: QueryService, principal: Principal) -> list[dict[str, Any]]:
    """Checks for sources that report stock status, source values, per-warehouse master data or coded values
    (e.g. SAP extracts). Each check runs only when the fields it needs are mapped."""
    mapping = query.mapping(principal.tenant_id)
    tenant = query.tenants.get(principal.tenant_id)
    action = "analysis:data_quality"
    checks: list[dict[str, Any]] = []
    cost = principal.has(Permission.COST_READ)

    def count(dataset: str, field: str, filters: list[dict[str, Any]]) -> int:
        plan = QueryPlan.model_validate(
            {"dataset": dataset, "measures": [{"field": field, "agg": "count", "alias": "n"}], "filters": filters}
        )
        return int(query.run_plan(plan, principal, action=action).rows[0]["n"])

    def check(check_id: str, title: str, n: int | None, status: str | None = None, **extra: Any) -> None:
        if status is None:
            status = "ok" if n == 0 else "issue"
        checks.append({"id": check_id, "title": title, "status": status, "count": n, **extra})

    master_join = next(
        (j for j in ("item_warehouse", "item") if mapping.has_ref("stock_balance", f"{j}.item_id")), None
    )
    if master_join is not None:
        n = count(
            "stock_balance",
            "item_id",
            [{"field": "quantity", "op": "ne", "value": "0"}, {"field": f"{master_join}.item_id", "op": "is_null"}],
        )
        title = (
            "Stock lines without master data for their warehouse"
            if master_join == "item_warehouse"
            else ("Stock lines whose item is missing from the item master")
        )
        check("stock_without_master", title, n)

    if mapping.field("stock_balance", "valuation_price") is not None:
        title = "Stock lines with a zero valuation price"
        if cost:
            n = count(
                "stock_balance",
                "item_id",
                [
                    {"field": "valuation_price", "op": "eq", "value": "0"},
                    {"field": "quantity", "op": "ne", "value": "0"},
                ],
            )
            check("zero_valuation_price", title, n)
        else:
            check("zero_valuation_price", title, None, "restricted")

    if all(mapping.field("stock_balance", f) is not None for f in ("source_value", "valuation_price", "quantity")):
        title = "Source-reported values that differ from quantity × price"
        if cost:
            tol = tenant.policies.value_tolerance
            mismatched, compared = _value_mismatches(query, principal, tol)
            rounding = mapping.field("stock_balance", "price_rounding") is not None
            rule = f"{tol} + |quantity| × price rounding" if rounding else str(tol)
            check("source_value_mismatch", title, mismatched, compared=compared, tolerance=rule)
        else:
            check("source_value_mismatch", title, None, "restricted")

    key = [
        f
        for f in ("item_id", "warehouse_id", "location_id", "lot_id", "stock_status")
        if mapping.field("stock_balance", f)
    ]
    dup = query.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "stock_balance",
                "dimensions": key,
                "measures": [{"field": "item_id", "agg": "count", "alias": "lines"}],
                "having": [{"measure": "lines", "op": "gt", "value": 1}],
                "limit": 5,
            }
        ),
        principal,
        action=action,
        with_total=True,
    )
    n_dup = int((dup.page or {}).get("total") or 0)
    check(
        "duplicate_stock_keys",
        "Stock keys (" + ", ".join(key) + ") that appear on more than one line",
        n_dup,
        examples=[
            {"item_id": r["item_id"], "item_code": r["item_id"], "problems": [f"{r['lines']} lines"]} for r in dup.rows
        ],
    )

    for ds, fields in mapping.value_maps().items():
        for field in fields:
            n = count(ds, field, [{"field": field, "op": "eq", "value": UNMAPPED}])
            check(f"unmapped_{ds}_{field}", f"{ds}.{field}: source codes without a value map", n)

    if mapping.is_mapped("item_warehouse"):
        total = count("item_warehouse", "item_id", [])
        if mapping.field("item_warehouse", "abc_class") is not None:
            n = count("item_warehouse", "item_id", [{"field": "abc_class", "op": "is_null"}])
            check("missing_abc_warehouse", "Item–warehouse records without an ABC class", n, share=_share(n, total))
        if mapping.field("item_warehouse", "planning_type") is not None:
            n = count("item_warehouse", "item_id", [{"field": "planning_type", "op": "eq", "value": "none"}])
            check(
                "no_planning",
                "Item–warehouse records with no stock planning (planning type 'none')",
                n,
                "info",
                share=_share(n, total),
            )
        n = _master_without_stock(query, principal)
        check(
            "master_without_stock", "Item–warehouse master records without any stock", n, "info", share=_share(n, total)
        )
    return checks


def _scope_filter(principal: Principal, col: ColumnElement[Any]) -> list[ColumnElement[Any]]:
    if principal.scope.all:
        return []
    if not principal.scope.ids:
        raise ForbiddenError("forbidden_scope", "No warehouses are assigned to your account.")
    return [col.in_(sorted(principal.scope.ids))]


def _value_mismatches(query: QueryService, principal: Principal, tolerance: Decimal) -> tuple[int, int]:
    mapping = query.mapping(principal.tenant_id)
    sb = mapping.table("stock_balance").alias("sb")

    def c(name: str) -> ColumnElement[Any]:
        return mapping.column_expr("stock_balance", name, sb)

    compared = [
        c("source_value").is_not(None),
        c("valuation_price").is_not(None),
        *_scope_filter(principal, c("warehouse_id")),
    ]
    diff = c("source_value") - c("quantity") * c("valuation_price")
    # Differences explained by the source showing a rounded price are not mismatches (|quantity| × price rounding).
    bound: ColumnElement[Any] = sa.literal(tolerance, sa.Numeric(18, 4))
    if mapping.field("stock_balance", "price_rounding") is not None:
        qty = c("quantity")
        bound = bound + sa.case((qty < 0, -qty), else_=qty) * sa.func.coalesce(c("price_rounding"), 0)
    counts = []
    for extra in ([], [sa.or_(diff > bound, diff < -bound)]):
        stmt = sa.select(sa.func.count().label("n")).select_from(sb).where(*compared, *extra)
        raw = query.execute_select(
            principal, stmt, action="analysis:data_quality", dataset="stock_balance", fetch_limit=1
        )
        counts.append(int(raw.rows[0][0]))
    return counts[1], counts[0]


def _master_without_stock(query: QueryService, principal: Principal) -> int:
    mapping = query.mapping(principal.tenant_id)
    iw = mapping.table("item_warehouse").alias("iw")
    sb = mapping.table("stock_balance").alias("sb")

    def c(ds: str, name: str, table: Any) -> ColumnElement[Any]:
        return mapping.column_expr(ds, name, table)

    stocked = (
        sa.select(
            c("stock_balance", "item_id", sb).label("item_id"),
            c("stock_balance", "warehouse_id", sb).label("warehouse_id"),
        )
        .where(c("stock_balance", "quantity", sb) != 0)
        .distinct()
        .subquery("stocked")
    )
    on = sa.and_(
        stocked.c.item_id == c("item_warehouse", "item_id", iw),
        stocked.c.warehouse_id == c("item_warehouse", "warehouse_id", iw),
    )
    stmt = (
        sa.select(sa.func.count().label("n"))
        .select_from(iw.outerjoin(stocked, on))
        .where(stocked.c.item_id.is_(None), *_scope_filter(principal, c("item_warehouse", "warehouse_id", iw)))
    )
    raw = query.execute_select(principal, stmt, action="analysis:data_quality", dataset="item_warehouse", fetch_limit=1)
    return int(raw.rows[0][0])


# --------------------------------------------------------------------------------------- computed ABC
def run_abc(
    query: QueryService, principal: Principal, *, a_cutoff: Decimal, b_cutoff: Decimal, currency: str | None
) -> dict[str, Any]:
    if not principal.has(Permission.COST_READ):
        raise ForbiddenError("forbidden_field", "Your role cannot view cost or value information.")
    try:
        config = AbcConfig(a_cutoff, b_cutoff)
    except ValueError as exc:
        raise AppError("invalid_request", str(exc), 422) from exc
    filters: list[dict[str, Any]] = [{"field": "quantity", "op": "gt", "value": "0"}]
    if currency:
        filters.append({"field": "currency", "op": "eq", "value": currency})
    values_res = query.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "stock_balance",
                "dimensions": ["item_id"],
                "measures": [{"field": "stock_value", "agg": "sum", "alias": "value"}],
                "filters": filters,
                "limit": 1000,
            }
        ),
        principal,
        action="analysis:abc",
        metric=MetricRef("abc_computed", 1, "draft", ABC_RULE),
    )
    currencies = sorted({str(r["currency"]) for r in values_res.rows if r.get("currency")})
    if len(currencies) > 1:
        raise AppError(
            "abc_mixed_currency",
            f"Values are held in several currencies ({', '.join(currencies)}). Choose one currency; values are never converted.",
            409,
        )
    if values_res.truncated:
        raise AppError(
            "analysis_too_large",
            "Too many items for this method in one request (large runs arrive with background reports).",
            409,
        )
    values: dict[str, Decimal] = {}
    for row in values_res.rows:
        v = _dec(row["value"])
        if v is not None:
            values[str(row["item_id"])] = values.get(str(row["item_id"]), Decimal(0)) + v
    computed = classify(values, config)
    assigned: dict[str, str | None] = {}
    if query.mapping(principal.tenant_id).field("item", "abc_class") is not None:
        a_res = query.run_plan(
            QueryPlan.model_validate({"dataset": "item", "dimensions": ["item_id", "abc_class"], "limit": 1000}),
            principal,
            action="analysis:abc",
        )
        assigned = {str(r["item_id"]): (str(r["abc_class"]) if r["abc_class"] else None) for r in a_res.rows}
    matrix: dict[str, dict[str, int]] = {}
    items = []
    for item_id, cls in sorted(computed.items(), key=lambda kv: (-(values.get(kv[0]) or 0), kv[0])):
        a = assigned.get(item_id)
        matrix.setdefault(cls or "none", {}).setdefault(a or "none", 0)
        matrix[cls or "none"][a or "none"] += 1
        items.append(
            {
                "item_id": item_id,
                "value": _money(values.get(item_id), 2),
                "computed": cls,
                "assigned": a,
                "differs": a is not None and a != cls,
            }
        )
    return {
        "currency": currencies[0] if currencies else currency,
        "config": {
            "a_cutoff": str(a_cutoff),
            "b_cutoff": str(b_cutoff),
            "value_definition": "on-hand value (quantity × source valuation price)",
        },
        "items": items[:200],
        "item_count": len(items),
        "differences": sum(1 for i in items if i["differs"]),
        "matrix": matrix,
        "assigned_available": bool(assigned),
        "rule": ABC_RULE,
        "provenance": values_res.provenance,
        "warnings": [w.__dict__ for w in values_res.warnings if w.code != "auto_grouped"],
    }


# --------------------------------------------------------------------------------------- cost comparison
def run_cost_comparison(
    query: QueryService, principal: Principal, *, item_id: str, warehouse_id: str
) -> dict[str, Any]:
    if not principal.has(Permission.COST_READ):
        raise ForbiddenError("forbidden_field", "Your role cannot view cost or value information.")
    action = "analysis:cost_comparison"
    pair = [
        {"field": "item_id", "op": "eq", "value": item_id},
        {"field": "warehouse_id", "op": "eq", "value": warehouse_id},
    ]
    mv = query.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "inventory_transaction",
                "dimensions": ["txn_id", "txn_type", "quantity", "unit_cost", "posting_date"],
                "filters": pair,
                "order_by": [{"field": "posting_date"}, {"field": "txn_id"}],
                "limit": query.tenants.get(principal.tenant_id).policies.max_rows,
            }
        ),
        principal,
        action=action,
        metric=MetricRef("cost_comparison", 1, "draft", "; ".join(f"{k}: {v}" for k, v in COST_RULES.items())),
    )
    if not mv.rows:
        raise AppError(
            "no_data", "No movements were found for this item in this warehouse (or it is outside your scope).", 404
        )
    if mv.truncated:
        raise AppError("analysis_too_large", "This item has too many movements to cost in one request.", 409)
    movements = [
        Movement(
            str(r["txn_id"]),
            str(r["txn_type"]),
            r["quantity"],
            _dec(r["unit_cost"]),
            r["posting_date"],
            str(r["currency"]) if r.get("currency") else None,
            str(r["uom"]) if r.get("uom") else None,
        )
        for r in mv.rows
    ]
    warnings: list[dict[str, str]] = [w.__dict__ for w in mv.warnings if w.code in ("stale_data", "unknown_freshness")]
    methods: dict[str, Any] = {}
    errors: dict[str, str] = {}
    try:
        mwa = moving_weighted_average(movements)
        methods["moving_weighted_average"] = {
            "quantity": _money(mwa.quantity, 3),
            "unit_cost": _money(mwa.unit_cost),
            "value": _money(mwa.value, 2),
        }
        warnings += [{"code": w.split(":")[0], "message": w} for w in mwa.warnings]
    except CostingError as exc:
        mwa = None
        errors["moving_weighted_average"] = f"{exc.code}: {exc}"
    try:
        fifo, layers = fifo_layers(movements)
        methods["fifo"] = {
            "quantity": _money(fifo.quantity, 3),
            "unit_cost": _money(fifo.unit_cost),
            "value": _money(fifo.value, 2),
            "layers": [
                {
                    "receipt_date": layer.receipt_date.isoformat(),
                    "quantity": _money(layer.quantity, 3),
                    "unit_cost": _money(layer.unit_cost),
                    "source": layer.source,
                }
                for layer in layers
            ],
        }
    except CostingError as exc:
        errors["fifo"] = f"{exc.code}: {exc}"
    receipt = latest_receipt_cost(movements)
    methods["latest_receipt_cost"] = (
        {"unit_cost": _money(receipt.unit_cost), "date": receipt.posting_date.isoformat(), "reference": receipt.txn_id}
        if receipt
        else None
    )

    purchases = (
        query.run_plan(
            QueryPlan.model_validate(
                {
                    "dataset": "purchase_record",
                    "dimensions": ["po_id", "order_date", "status", "unit_price"],
                    "filters": pair,
                    "limit": query.tenants.get(principal.tenant_id).policies.max_rows,
                }
            ),
            principal,
            action=action,
        )
        if query.mapping(principal.tenant_id).is_mapped("purchase_record")
        else None
    )
    purchase = None
    if purchases is not None:
        statuses = frozenset(query.tenants.get(principal.tenant_id).latest_price_statuses)
        purchase = latest_valid_purchase_price(
            [
                PurchaseLine(str(r["po_id"]), r["order_date"], str(r["status"]), _dec(r["unit_price"]))
                for r in purchases.rows
                if r["order_date"]
            ],
            statuses,
        )
        if purchases.truncated:
            warnings.append(
                {
                    "code": "partial_purchases",
                    "message": "Purchase history was truncated; the latest price may be wrong.",
                }
            )
    methods["latest_valid_purchase_price"] = (
        {
            "unit_price": _money(purchase.unit_price),
            "order_date": purchase.order_date.isoformat(),
            "reference": purchase.po_id,
        }
        if purchase
        else None
    )

    source = query.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "stock_balance",
                "measures": [
                    {"field": "quantity", "agg": "sum", "alias": "qty"},
                    {"field": "stock_value", "agg": "sum", "alias": "value"},
                ],
                "filters": pair,
            }
        ),
        principal,
        action=action,
    )
    src_row = source.rows[0] if source.rows else None
    src_qty, src_value = (_dec(src_row["qty"]), _dec(src_row["value"])) if src_row else (None, None)
    source_unit = (src_value / src_qty) if src_qty and src_value is not None and src_qty > 0 else None
    methods["source_valuation"] = {
        "quantity": _money(src_qty, 3),
        "unit_cost": _money(source_unit),
        "value": _money(src_value, 2),
    }

    reconciliation: dict[str, Any] = {"status": "not_computable"}
    if mwa is not None and mwa.unit_cost is not None and source_unit is not None:
        diff = mwa.unit_cost - source_unit
        reconciliation = {
            "status": "match" if abs(diff) <= RECONCILE_TOLERANCE and mwa.quantity == src_qty else "differs",
            "difference_unit_cost": _money(diff),
            "tolerance": str(RECONCILE_TOLERANCE),
            "quantity_matches": mwa.quantity == src_qty,
            "note": "Moving average recomputed from movements vs the valuation price in the source.",
        }
    lots_res = (
        query.run_plan(
            QueryPlan.model_validate(
                {
                    "dataset": "stock_balance",
                    "dimensions": ["lot_id", "quantity", "lot.receipt_date", "lot.unit_cost"],
                    "filters": [
                        *pair,
                        {"field": "quantity", "op": "gt", "value": "0"},
                        {"field": "lot_id", "op": "is_not_null"},
                    ],
                    "limit": 200,
                }
            ),
            principal,
            action=action,
        )
        if query.mapping(principal.tenant_id).field("lot", "unit_cost") is not None
        else None
    )
    lots = [
        {
            "lot_id": r["lot_id"],
            "quantity": _money(r["quantity"], 3),
            "receipt_date": to_json_value(r["lot.receipt_date"]),
            "unit_cost": _money(_dec(r["lot.unit_cost"])),
        }
        for r in (lots_res.rows if lots_res else [])
    ]
    currency = movements[0].currency
    return {
        "item_id": item_id,
        "warehouse_id": warehouse_id,
        "currency": currency,
        "uom": movements[0].uom,
        "movements_used": len(movements),
        "methods": methods,
        "errors": errors,
        "reconciliation": reconciliation,
        "lots": lots,
        "rules": COST_RULES,
        "status": "draft — definitions await customer approval",
        "warnings": warnings,
        "provenance": mv.provenance,
    }
