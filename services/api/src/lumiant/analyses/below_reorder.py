"""Below-reorder analysis v1 (docs/04-domain/INVENTORY_CALCULATIONS.md).

Hand-written SQL shape (policy LEFT JOIN aggregated on-hand, so items with a policy and *no* stock lines
appear with on-hand 0), but built from the same pieces as every plan: tenant mapping, injected warehouse
scope, SQL guard, read-only connector, provenance and audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement

from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError, ForbiddenError
from lumiant.query.compiler import ExactDecimal
from lumiant.query.plan import Op
from lumiant.query.results import Column, QueryResult, ResultWarning
from lumiant.query.service import MetricRef, QueryService, meta_warnings
from lumiant.query.validator import AppliedFilter, FieldRef

ID, VERSION = "below_reorder", 1
EXCESS_ID = "excess_stock"
EXCESS_RULE = (
    "Item–warehouse pairs that have a customer maximum-stock policy, where on-hand quantity (sum of stock lines "
    "in the item's base unit) is above that maximum. Pairs without a maximum are never flagged."
)
RULE = (
    "Item–warehouse pairs that have a customer reorder policy, where on-hand quantity (sum of stock lines "
    "in the item's base unit; 0 when there are none) is below the reorder level. Pairs without a policy "
    "are never flagged; they are counted separately."
)
REQUIRED = {
    "reorder_policy": ("item_id", "warehouse_id", "reorder_level"),
    "stock_balance": ("item_id", "warehouse_id", "quantity", "uom"),
    "item": ("item_id", "base_uom"),
}


@dataclass(frozen=True)
class BelowReorderFilters:
    warehouses: tuple[str, ...] = ()
    item_groups: tuple[str, ...] = ()
    abc_classes: tuple[str, ...] = ()
    stages: tuple[str, ...] = ()


def run_below_reorder(
    query: QueryService,
    principal: Principal,
    filters: BelowReorderFilters,
    *,
    limit: int,
    offset: int,
    mode: Literal["below", "excess"] = "below",
) -> QueryResult:
    mapping = query.mapping(principal.tenant_id)
    below = mode == "below"
    analysis_id, rule = (ID, RULE) if below else (EXCESS_ID, EXCESS_RULE)
    limit_field = "reorder_level" if below else "max_stock"
    action = f"analysis:{analysis_id}"
    required = {**REQUIRED, "reorder_policy": ("item_id", "warehouse_id", limit_field)}
    for ds, needed in required.items():
        if not mapping.is_mapped(ds) or any(mapping.field(ds, f) is None for f in needed):
            raise AppError(
                "analysis_unavailable",
                "This analysis needs reorder policies, stock balances and item units, which are not all mapped "
                "for this tenant.",
                409,
            )
    if not principal.scope.all and any(not principal.scope.allows(w) for w in filters.warehouses):
        query.record(principal, action, "reorder_policy", "deny", "denied", reason="forbidden_scope")
        raise ForbiddenError("forbidden_scope", "You do not have access to one or more of those warehouses.")
    if not principal.scope.all and not principal.scope.ids:
        raise ForbiddenError("forbidden_scope", "No warehouses are assigned to your account.")

    def c(ds: str, name: str, table: Any) -> ColumnElement[Any]:
        return mapping.column_expr(ds, name, table)

    def opt(ds: str, name: str, table: Any, label: str) -> ColumnElement[Any]:
        return (c(ds, name, table) if mapping.field(ds, name) is not None else sa.null()).label(label)

    rp = mapping.table("reorder_policy").alias("rp")
    sb = mapping.table("stock_balance").alias("sb")
    it = mapping.table("item").alias("it")
    it_uom = mapping.table("item").alias("it_uom")
    has_wh = mapping.is_mapped("warehouse") and mapping.field("warehouse", "name") is not None
    wh = mapping.table("warehouse").alias("wh") if has_wh else None

    scope_ids = sorted(principal.scope.ids)

    def scoped(col: ColumnElement[Any]) -> list[ColumnElement[Any]]:
        conds: list[ColumnElement[Any]] = [] if principal.scope.all else [col.in_(scope_ids)]
        if filters.warehouses:
            conds.append(col.in_(list(filters.warehouses)))
        return conds

    same_uom = c("stock_balance", "uom", sb) == c("item", "base_uom", it_uom)
    onhand = (
        sa.select(
            c("stock_balance", "item_id", sb).label("item_id"),
            c("stock_balance", "warehouse_id", sb).label("warehouse_id"),
            sa.func.sum(c("stock_balance", "quantity", sb)).label("on_hand"),
        )
        .select_from(sb.join(it_uom, c("stock_balance", "item_id", sb) == c("item", "item_id", it_uom)))
        .where(same_uom, *scoped(c("stock_balance", "warehouse_id", sb)))
        .group_by(c("stock_balance", "item_id", sb), c("stock_balance", "warehouse_id", sb))
        .cte("onhand")
    )
    on_hand = sa.func.coalesce(onhand.c.on_hand, 0)
    level = c("reorder_policy", limit_field, rp)
    joined = rp.outerjoin(
        onhand,
        sa.and_(
            onhand.c.item_id == c("reorder_policy", "item_id", rp),
            onhand.c.warehouse_id == c("reorder_policy", "warehouse_id", rp),
        ),
    ).outerjoin(it, c("item", "item_id", it) == c("reorder_policy", "item_id", rp))
    if wh is not None:
        joined = joined.outerjoin(wh, c("warehouse", "warehouse_id", wh) == c("reorder_policy", "warehouse_id", rp))

    conditions = [
        level.is_not(None),
        (on_hand < level) if below else (on_hand > level),
        *scoped(c("reorder_policy", "warehouse_id", rp)),
    ]
    for values, field in (
        (filters.item_groups, "item_group"),
        (filters.abc_classes, "abc_class"),
        (filters.stages, "inventory_stage"),
    ):
        if values:
            if mapping.field("item", field) is None:
                raise AppError("field_not_available", f"'{field}' is not mapped for this tenant.", 400)
            conditions.append(c("item", field, it).in_(list(values)))

    exact = ExactDecimal()
    base = (
        sa.select(
            c("reorder_policy", "item_id", rp).label("item_id"),
            opt("item", "item_code", it, "item_code"),
            opt("item", "description", it, "description"),
            opt("item", "item_group", it, "item_group"),
            opt("item", "abc_class", it, "abc_class"),
            opt("item", "inventory_stage", it, "inventory_stage"),
            c("reorder_policy", "warehouse_id", rp).label("warehouse_id"),
            (c("warehouse", "name", wh) if wh is not None else sa.null()).label("warehouse_name"),
            c("item", "base_uom", it).label("uom"),
            sa.type_coerce(on_hand, exact).label("on_hand"),
            sa.type_coerce(level, exact).label(limit_field),
            sa.type_coerce((level - on_hand) if below else (on_hand - level), exact).label(
                "shortfall" if below else "excess"
            ),
        )
        .select_from(joined)
        .where(*conditions)
    )
    stmt = (
        base.order_by(
            ((on_hand / sa.func.nullif(level, 0)).asc() if below else (on_hand / sa.func.nullif(level, 0)).desc()),
            c("reorder_policy", "item_id", rp),
            c("reorder_policy", "warehouse_id", rp),
        )
        .limit(limit + 1)
        .offset(offset)
    )
    count_stmt = sa.select(sa.func.count().label("total")).select_from(base.subquery("q"))

    # Pairs with stock in scope but no usable policy (master-data gap, reported, never flagged).
    pairs = (
        sa.select(
            c("stock_balance", "item_id", sb).label("item_id"), c("stock_balance", "warehouse_id", sb).label("wh")
        )
        .where(*scoped(c("stock_balance", "warehouse_id", sb)))
        .distinct()
        .subquery("pairs")
    )
    rp2 = mapping.table("reorder_policy").alias("rp2")
    no_policy_stmt = (
        sa.select(sa.func.count().label("n"))
        .select_from(
            pairs.outerjoin(
                rp2,
                sa.and_(
                    c("reorder_policy", "item_id", rp2) == pairs.c.item_id,
                    c("reorder_policy", "warehouse_id", rp2) == pairs.c.wh,
                ),
            )
        )
        .where(
            sa.or_(c("reorder_policy", "item_id", rp2).is_(None), c("reorder_policy", "reorder_level", rp2).is_(None))
        )
    )
    sb2 = mapping.table("stock_balance").alias("sb2")
    it2 = mapping.table("item").alias("it2")
    mismatch_stmt = (
        sa.select(sa.func.count().label("n"))
        .select_from(sb2.join(it2, c("stock_balance", "item_id", sb2) == c("item", "item_id", it2)))
        .where(
            c("stock_balance", "uom", sb2) != c("item", "base_uom", it2),
            *scoped(c("stock_balance", "warehouse_id", sb2)),
        )
    )

    def scalar(select: sa.Select[Any]) -> int:
        result = query.execute_select(
            principal, select, action=action, dataset="reorder_policy", fetch_limit=1, audit=False
        )
        return int(result.rows[0][0])

    raw = query.execute_select(principal, stmt, action=action, dataset="reorder_policy", fetch_limit=limit + 1)
    total, no_policy, mismatched = scalar(count_stmt), scalar(no_policy_stmt), scalar(mismatch_stmt)

    truncated = len(raw.rows) > limit
    rows = [dict(zip(raw.columns, r, strict=True)) for r in raw.rows[:limit]]
    for row in rows:
        lvl, oh = row[limit_field], row["on_hand"]
        row["coverage_pct"] = (
            (Decimal(oh) / Decimal(lvl) * 100).quantize(Decimal("0.1"), ROUND_HALF_EVEN) if lvl else None
        )

    meta = query.tenant_meta(principal.tenant_id)
    warnings = meta_warnings(meta)
    if mismatched:
        warnings.append(
            ResultWarning(
                "uom_mismatch",
                f"{mismatched} stock line(s) are in a different unit than the item's base unit and were not counted.",
            )
        )
    scope_field = mapping.field("reorder_policy", "warehouse_id")
    assert scope_field is not None  # checked in REQUIRED
    injected = (
        []
        if principal.scope.all
        else [AppliedFilter(FieldRef("warehouse_id", None, "reorder_policy", scope_field), Op.IN, scope_ids, "scope")]
    )
    user_filters = [
        AppliedFilter(FieldRef(ref, None, ds, fdef), Op.IN, list(values), "user")
        for ref, ds, values in (
            ("warehouse_id", "reorder_policy", filters.warehouses),
            ("item.item_group", "item", filters.item_groups),
            ("item.abc_class", "item", filters.abc_classes),
            ("item.inventory_stage", "item", filters.stages),
        )
        if values and (fdef := mapping.field(ds, ref.rpartition(".")[2])) is not None
    ]
    fields = {
        limit_field: mapping.physical_ref("reorder_policy", limit_field),
        "on_hand": f"SUM({mapping.physical_ref('stock_balance', 'quantity')}) where unit = item base unit",
        "uom": mapping.physical_ref("item", "base_uom"),
    }
    provenance = query.provenance(
        principal,
        mapping,
        meta,
        dataset="reorder_policy",
        source_datasets=["reorder_policy", "stock_balance", "item", *(["warehouse"] if wh is not None else [])],
        fields=fields,
        filters=[*user_filters, *injected],
        auto_grouped=[],
        metric=MetricRef(analysis_id, VERSION, "draft", rule),
        row_count=len(rows),
        truncated=truncated,
        duration_ms=raw.duration_ms,
        stmt=stmt,
        rule=rule,
    )
    query.record(principal, action, "reorder_policy", "allow", "ok", rows=len(rows), ms=raw.duration_ms)
    columns = [
        Column(name, kind, "dimension" if kind == "string" else "measure")
        for name, kind in (
            ("item_id", "string"),
            ("item_code", "string"),
            ("description", "string"),
            ("item_group", "string"),
            ("abc_class", "string"),
            ("inventory_stage", "string"),
            ("warehouse_id", "string"),
            ("warehouse_name", "string"),
            ("uom", "string"),
            ("on_hand", "decimal"),
            (limit_field, "decimal"),
            ("shortfall" if below else "excess", "decimal"),
            ("coverage_pct", "decimal"),
        )
    ]
    return QueryResult(
        columns,
        rows,
        provenance,
        warnings,
        truncated,
        page={"offset": offset, "limit": limit, "total": total},
        summary={"flagged": total, "pairs_without_policy": no_policy, "uom_mismatched_lines": mismatched},
    )
