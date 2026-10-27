"""ValidatedPlan → parameterized SQLAlchemy Core SELECT. Every value is a bound parameter."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from lumiant.canonical.catalog import FieldType
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.plan import Agg, Op
from lumiant.query.validator import AppliedFilter, FieldRef, FilterGroup, MeasureSpec, ValidatedPlan

LIKE_ESCAPE = "!"  # backslash is mis-rendered for DuckDB by the PG dialect (ADR-0005 spike)


class ExactDecimal(sa.types.TypeDecorator[Any]):
    """Drivers already return `Decimal`; SQLAlchemy's Numeric result processing may round to the declared
    scale (or go through float). Output columns use this type so values arrive exactly as the database
    computed them."""

    impl = sa.Numeric
    cache_ok = True

    def result_processor(self, dialect: sa.engine.Dialect, coltype: object) -> None:
        return None


def _exact(expr: ColumnElement[Any], ftype: FieldType) -> ColumnElement[Any]:
    return sa.type_coerce(expr, ExactDecimal()) if ftype is FieldType.DECIMAL else expr


def escape_like(text: str) -> str:
    return text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2).replace("%", f"{LIKE_ESCAPE}%").replace("_", f"{LIKE_ESCAPE}_")


def condition(col: ColumnElement[Any], op: Op, value: Any) -> ColumnElement[Any]:
    expr: ColumnElement[Any]
    match op:
        case Op.EQ:
            expr = col == value
        case Op.NE:
            expr = col != value
        case Op.IN:
            expr = col.in_(value)
        case Op.NOT_IN:
            expr = col.not_in(value)
        case Op.LT:
            expr = col < value
        case Op.LTE:
            expr = col <= value
        case Op.GT:
            expr = col > value
        case Op.GTE:
            expr = col >= value
        case Op.BETWEEN:
            expr = col.between(value[0], value[1])
        case Op.IS_NULL:
            expr = col.is_(None)
        case Op.IS_NOT_NULL:
            expr = col.is_not(None)
        case Op.CONTAINS:
            expr = col.ilike(f"%{escape_like(value)}%", escape=LIKE_ESCAPE)
        case _:
            raise ValueError(f"unsupported operator {op}")
    return expr


class _Sources:
    def __init__(self, vp: ValidatedPlan, mapping: TenantMapping) -> None:
        self.mapping = mapping
        base = mapping.table(vp.dataset.name).alias("b")
        self.by_join: dict[str | None, FromClause] = {None: base}
        joined: FromClause = base
        for name in vp.joins:
            jdef = vp.dataset.joins[name]
            target = mapping.table(jdef.dataset).alias(f"j_{name}")
            on = sa.and_(
                *(
                    mapping.column_expr(vp.dataset.name, local, base)
                    == mapping.column_expr(jdef.dataset, remote, target)
                    for local, remote in jdef.on
                )
            )
            joined = joined.outerjoin(target, on)
            self.by_join[name] = target
        self.from_clause = joined

    def expr(self, ref: FieldRef) -> ColumnElement[Any]:
        return self.mapping.column_expr(ref.dataset, ref.fdef.name, self.by_join[ref.join])


def _aggregate(m: MeasureSpec, src: _Sources) -> ColumnElement[Any]:
    col = src.expr(m.field)
    match m.agg:
        case Agg.SUM:
            return sa.func.sum(col)
        case Agg.AVG:
            return sa.func.avg(col)
        case Agg.MIN:
            return sa.func.min(col)
        case Agg.MAX:
            return sa.func.max(col)
        case Agg.COUNT:
            return sa.func.count(col)
        case Agg.COUNT_DISTINCT:
            return sa.func.count(sa.distinct(col))
    raise ValueError(f"unsupported aggregation {m.agg}")


def _filter_expr(f: AppliedFilter | FilterGroup, src: _Sources) -> ColumnElement[Any]:
    if isinstance(f, FilterGroup):
        return sa.or_(*(condition(src.expr(g.field), g.op, g.value) for g in f.any_of))
    return condition(src.expr(f.field), f.op, f.value)


def compile_plan(vp: ValidatedPlan, mapping: TenantMapping, *, count_only: bool = False) -> sa.Select[Any]:
    """Build the SELECT. `count_only` returns the total row count of the same filtered result."""
    src = _Sources(vp, mapping)
    measure_exprs = {m.alias: _aggregate(m, src) for m in vp.measures}
    out_types = {m.alias: m.out_type for m in vp.measures}
    columns = [_exact(src.expr(d), d.fdef.type).label(d.ref) for d in vp.dimensions]
    columns += [_exact(expr, out_types[alias]).label(alias) for alias, expr in measure_exprs.items()]

    stmt = sa.select(*columns).select_from(src.from_clause)
    for f in vp.filters:
        stmt = stmt.where(_filter_expr(f, src))
    if vp.aggregate and vp.dimensions:
        stmt = stmt.group_by(*(src.expr(d) for d in vp.dimensions))
    for h in vp.having:
        stmt = stmt.having(condition(measure_exprs[h.measure.alias], h.op, h.value))

    if count_only:
        return sa.select(sa.func.count().label("total")).select_from(stmt.subquery("q"))

    for o in vp.order_by:
        target = measure_exprs[o.name] if isinstance(o.target, MeasureSpec) else src.expr(o.target)
        stmt = stmt.order_by(target.desc().nulls_last() if o.descending else target.asc().nulls_last())
    return stmt.limit(vp.limit + 1).offset(vp.offset)
