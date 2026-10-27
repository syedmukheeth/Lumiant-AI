"""Computed ABC classification. No defaults: the customer must approve cutoffs, value definition and period."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class AbcConfig:
    a_cutoff: Decimal  # cumulative share of total value covered by class A, e.g. 0.80
    b_cutoff: Decimal  # cumulative share covered by A+B, e.g. 0.95

    def __post_init__(self) -> None:
        if not (Decimal(0) < self.a_cutoff < self.b_cutoff <= Decimal(1)):
            raise ValueError("cutoffs must satisfy 0 < a_cutoff < b_cutoff <= 1")


def classify(values: dict[str, Decimal], config: AbcConfig) -> dict[str, str | None]:
    """Rank by value (ties by id), classify by cumulative share *before* adding the item, so the item that
    crosses a cutoff stays in the higher class. Items with value <= 0 are unclassified (None)."""
    positive = {k: v for k, v in values.items() if v > 0}
    total = sum(positive.values(), Decimal(0))
    result: dict[str, str | None] = dict.fromkeys(values)
    cumulative = Decimal(0)
    for item_id, value in sorted(positive.items(), key=lambda kv: (-kv[1], kv[0])):
        share_before = cumulative / total
        result[item_id] = "A" if share_before < config.a_cutoff else "B" if share_before < config.b_cutoff else "C"
        cumulative += value
    return result
