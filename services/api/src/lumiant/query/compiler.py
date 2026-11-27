"""ValidatedPlan → parameterized SQLAlchemy Core SELECT. Every value is a bound parameter."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import CompileError
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.compiler import SQLCompiler
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause
from sqlalchemy.sql.visitors import InternalTraversal, _TraverseInternalsType

from lumiant.canonical.catalog import FieldType
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.plan import PERIOD, Agg, Grain, Op
from lumiant.query.validator import (
    AppliedFilter,
    FieldRef,
    FilterGroup,
    MeasureSpec,
    TimeBucketSpec,
    ValidatedPlan,
)

LIKE_ESCAPE = "!"  # backslash is mis-rendered for DuckDB by the PG dialect (ADR-0005 spike)


class DateBucket(ColumnElement[str]):
    """A date or timestamp as ISO period text (QueryPlan.time_bucket): 2026-11-27, 2026-11, 2026-Q4 or 2026.

    Rendered per dialect below. The format strings are constants picked by grain and render inline as literals, so
    SELECT, GROUP BY and ORDER BY carry identical text (bind parameters would differ between the three, and
    PostgreSQL would then refuse the grouping). The grain is part of the cache key, so a month plan never reuses a
    year plan's compiled SQL.
    """

    inherit_cache = True
    _traverse_internals: _TraverseInternalsType = [  # noqa: RUF012 (SQLAlchemy declares it an instance attribute)
        ("expr", InternalTraversal.dp_clauseelement),
        ("grain", InternalTraversal.dp_string),
    ]
    type = sa.String()

    def __init__(self, expr: ColumnElement[Any], grain: Grain) -> None:
        self.expr = expr
        self.grain = Grain(grain).value

    @property
    def _from_objects(self) -> list[FromClause]:
        return self.expr._from_objects


def _bucket_parts(element: DateBucket, compiler: SQLCompiler, **kw: Any) -> tuple[str, Grain]:
    return compiler.process(element.expr, **kw), Grain(element.grain)


def _lit(compiler: SQLCompiler, text: str) -> str:
    """A constant string literal, escaped for the dialect (doubles '%' where the driver uses %-style parameters)."""
    return compiler.render_literal_value(text, sa.String())


_STRFTIME = {Grain.DAY: "%Y-%m-%d", Grain.MONTH: "%Y-%m", Grain.YEAR: "%Y"}  # DuckDB, SQLite, MySQL
_TO_CHAR = {Grain.DAY: "YYYY-MM-DD", Grain.MONTH: "YYYY-MM", Grain.QUARTER: 'YYYY-"Q"Q', Grain.YEAR: "YYYY"}
_ISO_CHARS = {Grain.DAY: 10, Grain.MONTH: 7, Grain.YEAR: 4}  # leading characters of SQL Server style 126


@compiles(DateBucket, "duckdb")
def _bucket_duckdb(element: DateBucket, compiler: SQLCompiler, **kw: Any) -> str:
    x, grain = _bucket_parts(element, compiler, **kw)
    if grain is Grain.QUARTER:
        year, sep = _lit(compiler, "%Y"), _lit(compiler, "-Q")
        return f"strftime({x}, {year}) || {sep} || CAST(EXTRACT(quarter FROM {x}) AS VARCHAR)"
    return f"strftime({x}, {_lit(compiler, _STRFTIME[grain])})"


@compiles(DateBucket, "sqlite")
def _bucket_sqlite(element: DateBucket, compiler: SQLCompiler, **kw: Any) -> str:
    x, grain = _bucket_parts(element, compiler, **kw)
    if grain is Grain.QUARTER:  # integer division: months 1-3 → 1 … 10-12 → 4
        year, month, sep = _lit(compiler, "%Y"), _lit(compiler, "%m"), _lit(compiler, "-Q")
        return f"strftime({year}, {x}) || {sep} || ((CAST(strftime({month}, {x}) AS INTEGER) + 2) / 3)"
    return f"strftime({_lit(compiler, _STRFTIME[grain])}, {x})"


@compiles(DateBucket, "postgresql")
@compiles(DateBucket, "oracle")
def _bucket_to_char(element: DateBucket, compiler: SQLCompiler, **kw: Any) -> str:
    x, grain = _bucket_parts(element, compiler, **kw)  # both read "Q" as quarter and "..." as literal text
    return f"TO_CHAR({x}, {_lit(compiler, _TO_CHAR[grain])})"


@compiles(DateBucket, "mysql")
@compiles(DateBucket, "mariadb")
def _bucket_mysql(element: DateBucket, compiler: SQLCompiler, **kw: Any) -> str:
    x, grain = _bucket_parts(element, compiler, **kw)
    if grain is Grain.QUARTER:  # `||` is OR in MySQL
        year, sep = _lit(compiler, "%Y"), _lit(compiler, "-Q")
        return f"CONCAT(DATE_FORMAT({x}, {year}), {sep}, EXTRACT(QUARTER FROM {x}))"
    return f"DATE_FORMAT({x}, {_lit(compiler, _STRFTIME[grain])})"


@compiles(DateBucket, "mssql")
def _bucket_mssql(element: DateBucket, compiler: SQLCompiler, **kw: Any) -> str:
    x, grain = _bucket_parts(element, compiler, **kw)
    if grain is Grain.QUARTER:
        year = f"CONVERT(char(4), {x}, 126)"
        return f"{year} + {_lit(compiler, '-Q')} + CAST(DATEPART(quarter, {x}) AS char(1))"
    return f"CONVERT(char({_ISO_CHARS[grain]}), {x}, 126)"


@compiles(DateBucket)
def _bucket_unsupported(element: DateBucket, compiler: SQLCompiler, **kw: Any) -> str:
    # A new engine needs its own rendering (and a dialect-matrix entry); never guess a date format.
    raise CompileError(f"time buckets are not supported on the '{compiler.dialect.name}' dialect")


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


_TSQL = frozenset({"mssql", "tsql"})  # SQLAlchemy and sqlglot names for SQL Server


def _ordering(target: ColumnElement[Any], descending: bool, dialect: str) -> list[ColumnElement[Any]]:
    """Sort with nulls last on every dialect. T-SQL has no NULLS LAST, so a null flag sorts first."""
    if dialect in _TSQL:
        nulls = sa.case((target.is_(None), sa.literal_column("1")), else_=sa.literal_column("0"))
        return [nulls.asc(), target.desc() if descending else target.asc()]
    return [target.desc().nulls_last() if descending else target.asc().nulls_last()]


def compile_plan(
    vp: ValidatedPlan, mapping: TenantMapping, *, count_only: bool = False, dialect: str = "default"
) -> sa.Select[Any]:
    """Build the SELECT. `count_only` returns the total row count of the same filtered result.

    `dialect` is the target's SQLAlchemy dialect name; it only changes constructs a dialect lacks (null ordering).
    """
    src = _Sources(vp, mapping)
    measure_exprs = {m.alias: _aggregate(m, src) for m in vp.measures}
    out_types = {m.alias: m.out_type for m in vp.measures}
    tb = vp.time_bucket
    bucket = DateBucket(src.expr(tb.field), tb.grain) if tb is not None else None
    groupings = [*([bucket] if bucket is not None else []), *(src.expr(d) for d in vp.dimensions)]
    # Same column order as ValidatedPlan.columns: period, dimensions, measures.
    columns = [bucket.label(PERIOD)] if bucket is not None else []
    columns += [_exact(src.expr(d), d.fdef.type).label(d.ref) for d in vp.dimensions]
    columns += [_exact(expr, out_types[alias]).label(alias) for alias, expr in measure_exprs.items()]

    stmt = sa.select(*columns).select_from(src.from_clause)
    for f in vp.filters:
        stmt = stmt.where(_filter_expr(f, src))
    if vp.aggregate and groupings:
        stmt = stmt.group_by(*groupings)
    for h in vp.having:
        stmt = stmt.having(condition(measure_exprs[h.measure.alias], h.op, h.value))

    if count_only:
        return sa.select(sa.func.count().label("total")).select_from(stmt.subquery("q"))

    for o in vp.order_by:
        target: ColumnElement[Any]
        if isinstance(o.target, MeasureSpec):
            target = measure_exprs[o.name]
        elif isinstance(o.target, TimeBucketSpec):
            assert bucket is not None  # the validator only orders by a bucket the plan has
            target = bucket
        else:
            target = src.expr(o.target)
        stmt = stmt.order_by(*_ordering(target, o.descending, dialect))
    stmt = stmt.limit(vp.limit + 1)
    # OFFSET only when paging: SQL Server pages with OFFSET/FETCH, which needs ORDER BY (the validator enforces
    # an ordering for offset > 0); without OFFSET it uses TOP, so single-number plans need no ordering.
    return stmt.offset(vp.offset) if vp.offset > 0 else stmt
