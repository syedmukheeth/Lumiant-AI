"""Numeric grounding guard (value-add V4): every number in AI-written prose must exist in tool results."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")


def normalize(token: str) -> str | None:
    """Canonical form: no commas, no trailing zeros ('10.0500' → '10.05', '2,767' → '2767')."""
    try:
        d = Decimal(token.replace(",", ""))
    except InvalidOperation:
        return None
    if not d.is_finite():
        return None
    text = format(d.normalize(), "f")
    return "0" if text in ("-0", "") else text


def collect_numbers(value: Any, into: set[str] | None = None) -> set[str]:
    """Every numeric-looking scalar (and numbers inside strings) found anywhere in a structure."""
    found = into if into is not None else set()
    if isinstance(value, bool) or value is None:
        return found
    if isinstance(value, (int, float, Decimal)):
        n = normalize(str(value))
        if n is not None:
            found.add(n)
    elif isinstance(value, str):
        for m in _NUMBER.findall(value):
            n = normalize(m)
            if n is not None:
                found.add(n)
    elif isinstance(value, dict):
        for v in value.values():
            collect_numbers(v, found)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            collect_numbers(v, found)
    return found


DISPLAY_PLACES = (2, 3)  # money is shown to 2 decimals, quantities to at most 3


def with_display_roundings(evidence: set[str]) -> set[str]:
    """The evidence plus each value rounded half-up to the display precisions, so '1,128,850.12' is traced to the
    result value 1128850.11776790. Only rounding of a real result is accepted; nothing is computed."""
    out = set(evidence)
    for e in evidence:
        try:
            d = Decimal(e)
        except InvalidOperation:
            continue
        exponent = d.as_tuple().exponent
        if not isinstance(exponent, int):
            continue
        for places in DISPLAY_PLACES:
            if exponent < -places:
                n = normalize(str(d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)))
                if n is not None:
                    out.add(n)
    return out


def ungrounded_numbers(text: str, evidence: set[str]) -> list[str]:
    """Numbers in `text` that appear nowhere in the evidence (exactly, or rounded to a display precision). Small
    ordinals (0, 1) are allowed as words-in-numbers."""
    allowed = with_display_roundings(evidence)
    bad: list[str] = []
    for m in _NUMBER.findall(text):
        n = normalize(m)
        if n is None or n in ("0", "1"):
            continue
        if n not in allowed:
            bad.append(m)
    return bad
