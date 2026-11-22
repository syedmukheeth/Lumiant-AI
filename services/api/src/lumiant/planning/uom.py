"""Unit-of-measure conversion (scenario 82): never aggregate quantities without a known conversion."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from lumiant.planning.model import ONE, UomConversion


def convert(
    quantity: Decimal, from_uom: str, to_uom: str, item_id: str | None, conversions: Iterable[UomConversion]
) -> Decimal | None:
    """`quantity` in `to_uom`, or None when no item-specific or general conversion is known (direct or inverse)."""
    if not from_uom or not to_uom or from_uom.upper() == to_uom.upper():
        return quantity
    f, t = from_uom.upper(), to_uom.upper()
    rules = sorted(conversions, key=lambda c: c.item_id is None)  # item-specific rules win
    for c in rules:
        if c.item_id not in (None, item_id):
            continue
        if c.from_uom.upper() == f and c.to_uom.upper() == t:
            return quantity * c.factor
        if c.from_uom.upper() == t and c.to_uom.upper() == f and c.factor != 0:
            return quantity * (ONE / c.factor)
    return None
