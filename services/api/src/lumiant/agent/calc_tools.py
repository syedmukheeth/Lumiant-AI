"""`calculate`: derived figures computed by the application, never by the model (ADR-0013).

The model may ask for a sum, a difference, a ratio, a percentage change or a share of figures it has already
received in this question. It names each figure by reference to a result cell (`c<call>.r<row>.<field>`, the
references `model_view` shows) or, for a number, the number itself, which must already appear in the results or in
the user's question. The application looks the figures up, checks that units and currencies agree, computes in
Decimal, rounds half-up for display, and returns the result as a tool output. The result is therefore evidence the
grounding check can trace, and the model still never writes a number of its own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation
from typing import Any, Literal

from pydantic import Field, model_validator

from lumiant.agent.grounding import collect_numbers, normalize, with_display_roundings
from lumiant.agent.tools import TOOLS, ToolContext, ToolDef, ToolOutput, _amount, _Args, _col, _quantity, ref_rows
from lumiant.auth.permissions import Permission

_REF = re.compile(r"^c(\d{1,2})\.r(\d{1,4})\.([a-z_][a-z0-9_.]{0,79})$")
_MONEY_TEXT = re.compile(r"^([A-Z]{3}) (-?[\d,]+(?:\.\d+)?)$")
Op = Literal["sum", "difference", "ratio", "pct_change", "share"]
TWO = {"difference", "ratio", "pct_change", "share"}


class Operand(_Args):
    ref: str | None = Field(
        default=None, max_length=90, description="A result cell, e.g. c0.r2.value (call 0, row 2, field value)"
    )
    value: str | None = Field(
        default=None,
        max_length=40,
        pattern=r"^-?\d[\d,]*(\.\d+)?$",
        description="A number that already appears in the results or the question",
    )

    @model_validator(mode="after")
    def _one(self) -> Operand:
        if (self.ref is None) == (self.value is None):
            raise ValueError("give exactly one of ref or value")
        return self


class CalcArgs(_Args):
    op: Op = Field(
        description=(
            "sum: add all operands; difference: first minus second; ratio: first divided by second; pct_change: "
            "percentage change from first to second; share: first as a percentage of second"
        )
    )
    operands: list[Operand] = Field(min_length=2, max_length=20)
    label: str | None = Field(default=None, max_length=80, description="What the result is, in a few words")


@dataclass(frozen=True)
class _Figure:
    value: Decimal
    unit: str  # a currency code, a unit of measure, "count", "%", or "" for a bare number
    kind: str  # money | qty | count | pct | number
    label: str


class CalcError(Exception):
    pass


def _parse(raw: Any) -> Decimal | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        d = Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


def _cell(ctx: ToolContext, ref: str) -> _Figure:
    m = _REF.match(ref)
    if not m:
        raise CalcError(f"“{ref}” is not a result reference (use c<call>.r<row>.<field>, e.g. c0.r1.value).")
    call, row_no, field = int(m.group(1)), int(m.group(2)), m.group(3)
    if call >= len(ctx.prior) or not ctx.prior[call].ok:
        raise CalcError(f"There is no successful result c{call} in this question.")
    rows = ref_rows(ctx.prior[call])
    if row_no >= len(rows):
        raise CalcError(f"Result c{call} has no row {row_no}.")
    row, kinds = rows[row_no]
    if field not in row:
        raise CalcError(f"Row c{call}.r{row_no} has no field “{field}”.")
    raw, kind = row[field], kinds.get(field, "text")
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise CalcError(f"{ref} has no value.")
    if isinstance(raw, str) and (money := _MONEY_TEXT.match(raw.strip())):
        value = _parse(money.group(2))
        if value is None:
            raise CalcError(f"{ref} is not a number.")
        return _Figure(value, money.group(1), "money", ref)
    value = _parse(raw)
    if value is None:
        raise CalcError(f"{ref} is not a single number (it may hold several currencies).")
    if kind == "money":
        return _Figure(value, str(row.get("currency") or ""), "money", ref)
    if kind == "qty":
        return _Figure(value, str(row.get("uom") or ""), "qty", ref)
    if kind == "int":
        return _Figure(value, "count", "count", ref)
    if kind == "pct":
        return _Figure(value, "%", "pct", ref)
    return _Figure(value, "", "number", ref)


def _evidence(ctx: ToolContext) -> set[str]:
    numbers = collect_numbers(ctx.question)
    for out in ctx.prior:
        if out.ok:
            collect_numbers(out.data, numbers)
            for row, _kinds in ref_rows(out):
                collect_numbers(row, numbers)
    return numbers


def _literal(value: str, evidence: set[str]) -> _Figure:
    d = _parse(value)
    if d is None:
        raise CalcError(f"“{value}” is not a number.")
    allowed = with_display_roundings(evidence)
    if normalize(str(d)) not in allowed and normalize(value.replace(",", "")) not in allowed:
        raise CalcError(f"{value} does not appear in the results or the question, so I can't use it.")
    return _Figure(d, "", "number", value)


def _same_unit(figs: list[_Figure]) -> _Figure:
    first = figs[0]
    for f in figs[1:]:
        if f.unit != first.unit or (f.kind == "money") != (first.kind == "money"):
            a, b = first.unit or "a bare number", f.unit or "a bare number"
            what = "amounts in different currencies" if "money" in (f.kind, first.kind) else "different units"
            raise CalcError(f"Cannot combine {a} and {b}: {what} are never added or compared.")
    return first


def compute(op: str, figs: list[_Figure]) -> tuple[Decimal, str, str]:
    """(result, unit, kind). Rules: sums and differences need one unit; a ratio or share of two figures in the same
    unit is unitless; dividing by a bare number keeps the first figure's unit."""
    if op in TWO and len(figs) != 2:
        raise CalcError(f"{op} takes exactly two figures.")
    a = figs[0]
    try:
        if op == "sum":
            u = _same_unit(figs)
            return sum((f.value for f in figs), Decimal(0)), u.unit, u.kind
        b = figs[1]
        if op == "difference":
            u = _same_unit(figs)
            return a.value - b.value, u.unit, u.kind
        if op == "pct_change":
            _same_unit(figs)
            return (b.value - a.value) / a.value * 100, "%", "pct"
        if op == "ratio":
            if b.kind == "number" and b.unit == "":
                return a.value / b.value, a.unit, a.kind
            _same_unit(figs)
            return a.value / b.value, "", "ratio"
        # share: a as a percentage of b (b may be a bare number, e.g. a target the user typed)
        if not (b.kind == "number" and b.unit == ""):
            _same_unit(figs)
        return a.value / b.value * 100, "%", "pct"
    except (DivisionByZero, InvalidOperation, ZeroDivisionError) as exc:
        raise CalcError("That would divide by zero.") from exc


def _display(value: Decimal, unit: str, kind: str) -> tuple[str, str]:
    """(exact text kept as evidence, display text)."""
    if kind == "money":
        exact = str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        return exact, f"{unit} {_amount(value)}".strip()
    if kind == "qty":
        return _quantity(value).replace(",", ""), f"{_quantity(value)} {unit}".strip()
    if kind in ("pct", "ratio"):
        q = value.quantize(Decimal("0.1") if kind == "pct" else Decimal("0.0001"), rounding=ROUND_HALF_UP)
        return str(q), f"{q}%" if kind == "pct" else str(q)
    q = value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP).normalize()
    text = format(q, "f")
    return text, text


def calculate(ctx: ToolContext, a: CalcArgs) -> ToolOutput:
    label = a.label or a.op.replace("_", " ")
    try:
        evidence = _evidence(ctx)
        figs = [_cell(ctx, o.ref) if o.ref else _literal(o.value or "", evidence) for o in a.operands]
        value, unit, kind = compute(a.op, figs)
    except CalcError as exc:
        return ToolOutput("calculate", "Calculation", f"Not calculated: {exc}", ok=False)
    exact, shown = _display(value, unit, kind)
    rows = [{"figure": f.label, "value": _display(f.value, f.unit, f.kind)[1], "unit": f.unit or ""} for f in figs] + [
        {"figure": f"= {label}", "value": shown, "unit": unit}
    ]
    note = ""
    if a.op == "share" and figs[1].kind == "number" and figs[0].unit:
        note = f" This assumes {figs[1].label} is in {figs[0].unit}."
    block = {
        "type": "table",
        "title": f"Calculation: {label}",
        "columns": [_col("figure", "Figure"), _col("value", "Value"), _col("unit", "Unit")],
        "rows": rows,
    }
    return ToolOutput(
        "calculate",
        "Calculation",
        f"{label[:1].upper() + label[1:]}: {shown}.{note}",
        [block],
        data={"op": a.op, "result": exact, "display": shown, "unit": unit, "operands": rows[:-1]},
    )


CALC_TOOLS = (
    ToolDef(
        "calculate",
        "Compute a derived figure from figures you already received in this question: sum, difference, ratio, "
        "pct_change (from first to second) or share (first as % of second). Cite result cells as c<call>.r<row>."
        "<field> (shown as `ref` on each row), or a number that appears in the results or the question. The "
        "application computes exactly and refuses to mix currencies or units. Use it for every figure you derive.",
        CalcArgs,
        (Permission.INVENTORY_READ,),
        calculate,
    ),
)
TOOLS.update({t.name: t for t in CALC_TOOLS})
