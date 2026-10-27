"""Numeric grounding guard (value-add V4): every number in AI-written prose must exist in tool results."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
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


def ungrounded_numbers(text: str, evidence: set[str]) -> list[str]:
    """Numbers in `text` that appear nowhere in the evidence. Small ordinals (0, 1) are allowed as words-in-numbers."""
    bad: list[str] = []
    for m in _NUMBER.findall(text):
        n = normalize(m)
        if n is None or n in ("0", "1"):
            continue
        if n not in evidence:
            bad.append(m)
    return bad
