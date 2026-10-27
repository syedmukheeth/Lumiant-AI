"""Costing and ABC against hand-computed results (brief §18 edge cases)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from lumiant.costing.abc import AbcConfig, classify
from lumiant.costing.engine import (
    CostingError,
    Movement,
    PurchaseLine,
    fifo_layers,
    fifo_pick,
    latest_receipt_cost,
    latest_valid_purchase_price,
    moving_weighted_average,
    periodic_weighted_average,
    present,
)


def mv(txn: str, kind: str, qty: str, cost: str | None, day: int, month: int = 1, **kw: str) -> Movement:
    return Movement(txn, kind, D(qty), D(cost) if cost is not None else None, date(2026, month, day), **kw)


# Hand-computed scenario S1:
#   +10 @ 5.00 -> 10 @ 5.00 (value 50)
#   +10 @ 7.00 -> 20 @ (50+70)/20 = 6.00 (value 120)
#    -5        -> 15 @ 6.00 (value 90)
#    +5 @ 10.00-> 20 @ (90+50)/20 = 7.00 (value 140)
S1 = [
    mv("T1", "RECEIPT", "10", "5.00", 1),
    mv("T2", "RECEIPT", "10", "7.00", 2),
    mv("T3", "ISSUE", "-5", None, 3),
    mv("T4", "RECEIPT", "5", "10.00", 4),
]


def test_moving_weighted_average_hand_computed() -> None:
    r = moving_weighted_average(S1)
    assert (r.quantity, r.unit_cost, r.value) == (D(20), D(7), D(140))


def test_fifo_differs_from_average_as_expected() -> None:
    # After the issue FIFO keeps 5@5 + 10@7; then +5@10: value 25 + 70 + 50 = 145 (MWA says 140).
    result, layers = fifo_layers(S1)
    assert (result.quantity, result.value) == (D(20), D(145))
    assert [(layer.quantity, layer.unit_cost) for layer in layers] == [(D(5), D(5)), (D(10), D(7)), (D(5), D(10))]


def test_input_order_does_not_matter() -> None:
    assert moving_weighted_average(list(reversed(S1))).value == D(140)


def test_returns_and_positive_adjustments_come_back_at_current_average() -> None:
    r = moving_weighted_average(
        [mv("A", "RECEIPT", "10", "5", 1), mv("B", "ISSUE", "-4", None, 2), mv("C", "RETURN", "2", None, 3)]
    )
    assert (r.quantity, r.unit_cost, r.value) == (D(8), D(5), D(40))


def test_average_is_not_rounded_internally() -> None:
    r = moving_weighted_average([mv("A", "RECEIPT", "3", "1.00", 1), mv("B", "RECEIPT", "3", "1.01", 2)])
    assert r.unit_cost == D("1.005")
    assert present(r.unit_cost or D(0)) == D("1.0050")
    assert r.value == D("6.03")


@pytest.mark.parametrize(("raw", "expected"), [("0.12345", "0.1234"), ("0.12355", "0.1236"), ("2.5", "2.5000")])
def test_presentation_rounding_is_half_even(raw: str, expected: str) -> None:
    assert present(D(raw)) == D(expected)


def test_zero_quantity_movements_are_ignored_with_a_warning() -> None:
    r = moving_weighted_average([mv("A", "RECEIPT", "4", "2", 1), mv("Z", "ADJUSTMENT", "0", None, 2)])
    assert r.value == D(8)
    assert "zero_quantity:Z" in r.warnings


def test_exact_duplicates_are_dropped_conflicts_are_flagged() -> None:
    dup = mv("A", "RECEIPT", "4", "2", 1)
    r = moving_weighted_average([dup, dup, mv("A", "RECEIPT", "9", "9", 1)])
    assert r.quantity == D(4)
    assert "duplicate_transaction:A" in r.warnings
    assert "conflicting_duplicate:A" in r.warnings


def test_emptying_stock_has_no_average() -> None:
    r = moving_weighted_average([mv("A", "RECEIPT", "4", "2", 1), mv("B", "ISSUE", "-4", None, 2)])
    assert (r.quantity, r.unit_cost, r.value) == (D(0), None, D(0))


def test_next_receipt_after_empty_restarts_the_average() -> None:
    r = moving_weighted_average(
        [mv("A", "RECEIPT", "4", "2", 1), mv("B", "ISSUE", "-4", None, 2), mv("C", "RECEIPT", "1", "9", 3)]
    )
    assert r.unit_cost == D(9)


@pytest.mark.parametrize(
    ("movements", "code"),
    [
        ([mv("A", "RECEIPT", "1", "1", 1), mv("B", "ISSUE", "-2", None, 2)], "negative_stock"),
        ([mv("A", "RECEIPT", "1", None, 1)], "missing_cost"),
        ([mv("A", "RECEIPT", "1", "-1", 1)], "negative_cost"),
        ([mv("A", "RECEIPT", "-1", "1", 1)], "bad_sign"),
        (
            [mv("A", "RECEIPT", "1", "1", 1, currency="USD"), mv("B", "RECEIPT", "1", "1", 2, currency="EUR")],
            "mixed_currencies",
        ),
        ([mv("A", "RECEIPT", "1", "1", 1, uom="KG"), mv("B", "RECEIPT", "1", "1", 2, uom="EA")], "mixed_uom"),
    ],
)
def test_insufficient_or_unsafe_inputs_raise(movements: list[Movement], code: str) -> None:
    with pytest.raises(CostingError) as exc:
        moving_weighted_average(movements)
    assert exc.value.code == code


def test_fifo_negative_stock_raises() -> None:
    with pytest.raises(CostingError) as exc:
        fifo_layers([mv("A", "RECEIPT", "1", "1", 1), mv("B", "ISSUE", "-2", None, 2)])
    assert exc.value.code == "negative_stock"


# Periodic average, hand computed: opening 10 @ 5 (50) + in-period 10 @ 7 (70) = 120 / 20 = 6.00
def test_periodic_average_respects_period_boundaries() -> None:
    movements = [
        mv("BEFORE", "RECEIPT", "99", "99", 31, month=12 - 11),  # Jan 31 is before Feb 1: excluded
        mv("START", "RECEIPT", "4", "7", 1, month=2),  # on the start date: included
        mv("MID", "RECEIPT", "6", "7", 15, month=2),
        mv("END", "RECEIPT", "50", "100", 1, month=3),  # on the end date (exclusive): excluded
        mv("ISS", "ISSUE", "-3", None, 10, month=2),  # issues never change a periodic average
    ]
    r = periodic_weighted_average(movements, date(2026, 2, 1), date(2026, 3, 1), opening_qty=D(10), opening_value=D(50))
    assert (r.quantity, r.unit_cost, r.value) == (D(20), D(6), D(120))


def test_periodic_average_bad_period() -> None:
    with pytest.raises(CostingError):
        periodic_weighted_average([], date(2026, 3, 1), date(2026, 3, 1), opening_qty=D(0), opening_value=D(0))


def test_fifo_pick_takes_oldest_first() -> None:
    _, layers = fifo_layers(S1)
    picks = fifo_pick(layers, D(8))
    assert [(p[0].unit_cost, p[1]) for p in picks] == [(D(5), D(5)), (D(7), D(3))]
    with pytest.raises(CostingError):
        fifo_pick(layers, D(1000))


def test_latest_prices_are_different_definitions() -> None:
    lines = [
        PurchaseLine("PO1", date(2026, 1, 5), "RECEIVED", D("5.00")),
        PurchaseLine("PO2", date(2026, 3, 1), "OPEN", D("9.00")),  # newer but not a valid status
        PurchaseLine("PO3", date(2026, 2, 1), "RECEIVED", D("6.00")),
        PurchaseLine("PO4", date(2026, 4, 1), "RECEIVED", None),  # no price
    ]
    purchase = latest_valid_purchase_price(lines, frozenset({"RECEIVED"}))
    assert purchase is not None
    assert purchase.unit_price == D("6.00")
    receipt = latest_receipt_cost(S1)
    assert receipt is not None
    assert receipt.unit_cost == D(
        "10.00"
    )  # the receipt cost differs from the purchase price: both are shown, never mixed
    assert latest_valid_purchase_price([], frozenset({"RECEIVED"})) is None


# ABC, hand computed: values 800/100/50/30/20 (total 1000), cutoffs 0.80 / 0.95.
# share before: A=0 -> A; B=.80 -> B; C=.90 -> B; D=.95 -> C; E=.98 -> C.
def test_abc_hand_computed() -> None:
    values = {"A": D(800), "B": D(100), "C": D(50), "D": D(30), "E": D(20), "Z": D(0)}
    result = classify(values, AbcConfig(D("0.80"), D("0.95")))
    assert result == {"A": "A", "B": "B", "C": "B", "D": "C", "E": "C", "Z": None}


def test_abc_ties_are_deterministic_and_single_item_is_a() -> None:
    cfg = AbcConfig(D("0.5"), D("0.9"))
    assert classify({"b": D(10), "a": D(10)}, cfg) == {"a": "A", "b": "B"}
    assert classify({"only": D(5)}, cfg) == {"only": "A"}
    assert classify({}, cfg) == {}


def test_abc_has_no_default_thresholds_and_validates_them() -> None:
    with pytest.raises(TypeError):
        AbcConfig()  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="cutoffs"):
        AbcConfig(D("0.95"), D("0.8"))
