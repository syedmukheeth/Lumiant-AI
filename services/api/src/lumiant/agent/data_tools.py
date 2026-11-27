"""`query_inventory`: the model asks the query engine directly with a typed plan (ADR-0002).

The model fills a small, LLM-friendly argument shape; this module turns it into a `QueryPlan` and runs it through
the same validator, scope injection, SQL guard, audit and provenance as every dashboard query. The model never sees
SQL or physical names: it sees the canonical catalog (`catalog_note`), restricted to what this tenant maps and this
principal may read. Rejections come back as tool results, so the model can correct its plan in the next round.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, ValidationError

from lumiant.agent.tools import TOOLS, Block, ToolContext, ToolDef, ToolOutput, _Args, _col, _warn
from lumiant.auth.permissions import Permission
from lumiant.canonical.catalog import CATALOG, FieldDef, FieldRole, FieldType, Sensitivity
from lumiant.query.plan import PERIOD, QueryPlan

MAX_QUERY_ROWS = 100
_FIELD = r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)?$"
_ALIAS = r"^[a-z][a-z0-9_]{0,40}$"
Scalar = str | int | float | bool


class MeasureArg(_Args):
    field: str = Field(pattern=_FIELD, max_length=80, description="Measure field, e.g. quantity or stock_value")
    agg: Literal["sum", "count", "count_distinct", "min", "max", "avg"]
    alias: str | None = Field(default=None, pattern=_ALIAS, description="Short output name, e.g. total_value")


class FilterArg(_Args):
    field: str = Field(pattern=_FIELD, max_length=80)
    op: Literal["eq", "ne", "in", "not_in", "lt", "lte", "gt", "gte", "between", "is_null", "is_not_null", "contains"]
    value: Scalar | list[Scalar] | None = Field(
        default=None, description="One value; a list for in / not_in; [low, high] for between; dates as YYYY-MM-DD"
    )


class PeriodArg(_Args):
    field: str = Field(pattern=_FIELD, max_length=80, description="A date field of the dataset, e.g. posting_date")
    grain: Literal["day", "month", "quarter", "year"] = Field(
        description="Period length; the result gets a 'period' column such as 2026-11-27, 2026-11, 2026-Q4 or 2026"
    )


class QueryArgs(_Args):
    dataset: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$", description="Dataset name from the data catalog")
    group_by: list[str] = Field(
        default_factory=list, max_length=6, description="Fields to group by (or to list, when there are no measures)"
    )
    period: PeriodArg | None = Field(
        default=None,
        description="Group by time (e.g. month by month); oldest period first unless order_by is 'period'",
    )
    measures: list[MeasureArg] = Field(default_factory=list, max_length=6)
    filters: list[FilterArg] = Field(default_factory=list, max_length=10)
    order_by: str | None = Field(default=None, max_length=80, description="A group_by field or a measure alias")
    descending: bool = True
    limit: int = Field(default=25, ge=1, le=MAX_QUERY_ROWS)


def _scalar(value: Any) -> Any:
    """Floats from JSON become exact decimal strings: the plan refuses floats so no precision is lost."""
    if isinstance(value, float):
        return str(Decimal(repr(value)))
    return value


def to_plan(a: QueryArgs) -> QueryPlan:
    measures = [{"field": m.field, "agg": m.agg, **({"alias": m.alias} if m.alias else {})} for m in a.measures]
    filters = [
        {
            "field": f.field,
            "op": f.op,
            "value": [_scalar(v) for v in f.value] if isinstance(f.value, list) else _scalar(f.value),
        }
        for f in a.filters
    ]
    order = [{"field": a.order_by, "direction": "desc" if a.descending else "asc"}] if a.order_by else []
    bucket = {"time_bucket": {"field": a.period.field, "grain": a.period.grain}} if a.period else {}
    return QueryPlan.model_validate(
        {
            "dataset": a.dataset,
            "dimensions": a.group_by,
            **bucket,
            "measures": measures,
            "filters": filters,
            "order_by": order,
            "limit": a.limit,
        }
    )


def _field_def(dataset: str, ref: str) -> FieldDef | None:
    ds = CATALOG.get(dataset)
    if ds is None:
        return None
    join_name, _, name = ref.rpartition(".")
    if not join_name:
        return ds.fields.get(name)
    join = ds.joins.get(join_name)
    target = CATALOG.get(join.dataset) if join else None
    return target.fields.get(name) if target else None


def _kind(fdef: FieldDef | None, agg: str | None) -> str:
    if agg in ("count", "count_distinct"):
        return "int"
    if fdef is None:
        return "text"
    if fdef.currency_field:
        return "money"
    if fdef.unit_field:
        return "qty"
    if fdef.type is FieldType.INTEGER:
        return "int"
    if fdef.type in (FieldType.DATE, FieldType.DATETIME):
        return "date"
    if fdef.type is FieldType.DECIMAL:
        return "qty"
    return "text"


def _label(ref: str) -> str:
    return ref.replace(".", " ").replace("_", " ").strip().capitalize()


def _text(value: Any) -> Any:
    """Chart values travel as strings (decimals are already strings in the payload); nulls stay null."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, float):  # SQLite stand-in stores decimals as REAL
        return format(Decimal(repr(value)), "f")
    return str(value)


def _period_chart(plan: QueryPlan, result_columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> Block | None:
    """A line over periods for one money or quantity measure (contract with the web `ChartBlock`).

    Only when the plan groups by period alone (plus the currency / unit the engine adds), so each period is one point
    per unit; rows of different currencies or units stay apart through `unit_key`, never summed.
    """
    if plan.time_bucket is None or plan.dimensions or not rows:
        return None
    charted = []
    for m in plan.measures:
        fdef = _field_def(plan.dataset, m.field)
        kind = _kind(fdef, m.agg.value)
        if kind in ("money", "qty"):
            charted.append((m, fdef, kind))
    if len(charted) != 1:
        return None
    m, fdef, kind = charted[0]
    present = {c["name"] for c in result_columns}
    join, _, _ = m.field.rpartition(".")
    unit = (fdef.currency_field or fdef.unit_field) if fdef else None
    unit_ref = f"{join}.{unit}" if join and unit else unit
    label = m.name.replace("_", " ").capitalize()
    series: dict[str, Any] = {"key": m.name, "label": label, "kind": kind}
    if unit_ref and unit_ref in present:
        series["unit_key"] = unit_ref
    return {
        "type": "chart",
        "variant": "line",
        "title": f"{label} by {plan.time_bucket.grain.value}",
        "x_key": PERIOD,
        "series": [series],
        "rows": [{k: _text(v) for k, v in row.items()} for row in rows],
    }


def query_inventory(ctx: ToolContext, a: QueryArgs) -> ToolOutput:
    try:
        plan = to_plan(a)
    except ValidationError as exc:
        problem = exc.errors()[0].get("msg", "invalid plan") if exc.errors() else "invalid plan"
        return ToolOutput(
            "query_inventory",
            "Query",
            f"The query was not valid ({problem}). Check the field names in the data catalog.",
            ok=False,
        )
    res = ctx.query.run_plan(plan, ctx.principal, action="agent:query_inventory")
    payload = res.payload()
    rows: list[dict[str, Any]] = payload["data"]
    measure_names = {m.name: m for m in plan.measures}
    columns = []
    for c in payload["columns"]:
        m = measure_names.get(c["name"])
        fdef = _field_def(plan.dataset, m.field if m else c["name"])
        columns.append(
            _col(
                c["name"],
                m.name.replace("_", " ").capitalize() if m else _label(c["name"]),
                _kind(fdef, m.agg.value if m else None),
            )
        )
    title = CATALOG[plan.dataset].description.split(":")[0].rstrip(".") if plan.dataset in CATALOG else plan.dataset
    blocks: list[Block] = [{"type": "table", "title": title, "columns": columns, "rows": rows}]
    chart = _period_chart(plan, payload["columns"], rows)
    if chart is not None:
        blocks.append(chart)
    # One grouping and one money/quantity measure: also show it as bars (the unit stays attached to every bar).
    groups = list(plan.dimensions)
    if plan.time_bucket is None and len(groups) == 1 and len(plan.measures) == 1 and rows:
        m = plan.measures[0]
        kind = _kind(_field_def(plan.dataset, m.field), m.agg.value)
        unit_key = next((c["name"] for c in payload["columns"] if c["name"].endswith(("currency", "uom"))), None)
        if kind in ("money", "qty") and unit_key:
            blocks.insert(
                0,
                {
                    "type": "bar",
                    "title": title,
                    "label_key": groups[0],
                    "value_key": m.name,
                    "kind": kind,
                    "unit_key": unit_key,
                    "rows": rows[:15],
                },
            )
    truncated = " (more rows exist; narrow the question to see them)" if res.truncated else ""
    answer = f"The query returned {len(rows)} row{'s' if len(rows) != 1 else ''}{truncated}."
    return ToolOutput("query_inventory", title, answer, blocks, payload["provenance"], _warn(res), data=payload)


def catalog_note(ctx: ToolContext) -> str:
    """The canonical datasets and fields this tenant maps and this principal may read; no physical names."""
    mapping = ctx.query.mapping(ctx.principal.tenant_id)
    cost = ctx.principal.has(Permission.COST_READ)
    lines = []
    for ds in CATALOG.values():
        if not mapping.is_mapped(ds.name):
            continue
        fields = []
        for f in mapping.fields(ds.name).values():
            if f.sensitivity is Sensitivity.COST and not cost:
                continue
            tag = "measure" if f.role is FieldRole.MEASURE else f.type.value
            extra = (
                f", per {f.unit_field}" if f.unit_field else (f", per {f.currency_field}" if f.currency_field else "")
            )
            fields.append(f"{f.name} ({tag}{extra}): {f.description[:70]}")
        joins = [j for j, jd in ds.joins.items() if mapping.is_mapped(jd.dataset)]
        join_text = f" Joined fields: {', '.join(j + '.<field>' for j in joins)}." if joins else ""
        dates = [f.name for f in mapping.fields(ds.name).values() if f.type in (FieldType.DATE, FieldType.DATETIME)]
        period_text = f" Period fields: {', '.join(dates)}." if dates else ""
        lines.append(f"- {ds.name}: {ds.description}{join_text}{period_text}\n    " + "\n    ".join(fields))
    return (
        "\n\nData catalog for query_inventory (canonical names; amounts are always kept per currency and quantities "
        "per unit, which the engine adds automatically). To answer over time (e.g. month by month), pass period "
        "{field: <one of the dataset's period fields>, grain: day|month|quarter|year}; rows then carry a 'period' "
        "column (2026-11-27, 2026-11, 2026-Q4, 2026), oldest first:\n" + "\n".join(lines)
    )


DATA_TOOLS = (
    ToolDef(
        "query_inventory",
        "Ask the inventory data directly with a typed query when no named analysis fits: choose a dataset from the "
        "data catalog, fields to group by, measures (sum, count, count_distinct, min, max, avg) and filters. The "
        "platform validates it, applies the user's access scope and returns rows. Never use it to guess figures.",
        QueryArgs,
        (Permission.INVENTORY_READ,),
        query_inventory,
    ),
)
TOOLS.update({t.name: t for t in DATA_TOOLS})
