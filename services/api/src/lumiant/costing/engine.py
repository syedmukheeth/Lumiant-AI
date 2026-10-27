"""Deterministic costing (docs/04-domain/INVENTORY_CALCULATIONS.md). Pure functions on `Decimal`, no I/O.

Every rule here is a DRAFT definition awaiting customer approval (D-002). Nothing is rounded internally;
`present()` is the only place that rounds (half-even, 4 dp for unit cost, 2 dp for money).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

ZERO = Decimal(0)
ADD_AT_COST = {"RECEIPT", "TRANSFER_IN"}
REMOVE = {"ISSUE", "TRANSFER_OUT"}


class CostingError(Exception):
    """Inputs are not sufficient for a defensible number. `code` is safe to show."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Movement:
    txn_id: str
    txn_type: str
    quantity: Decimal  # signed: + in, - out
    unit_cost: Decimal | None
    posting_date: date
    currency: str | None = None
    uom: str | None = None


@dataclass
class CostResult:
    quantity: Decimal
    unit_cost: Decimal | None  # None when quantity is zero (no meaningful average)
    value: Decimal
    warnings: list[str] = field(default_factory=list)


def present(value: Decimal, places: int = 4) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-places), ROUND_HALF_EVEN)


def prepare(movements: list[Movement]) -> tuple[list[Movement], list[str]]:
    """Order by (date, txn_id) and drop exact duplicates of the same document id; report both."""
    warnings: list[str] = []
    seen: dict[str, Movement] = {}
    out: list[Movement] = []
    for m in sorted(movements, key=lambda m: (m.posting_date, m.txn_id)):
        prior = seen.get(m.txn_id)
        if prior is not None:
            warnings.append(f"duplicate_transaction:{m.txn_id}" if prior == m else f"conflicting_duplicate:{m.txn_id}")
            continue
        seen[m.txn_id] = m
        out.append(m)
    currencies = {m.currency for m in out if m.currency}
    uoms = {m.uom for m in out if m.uom}
    if len(currencies) > 1:
        raise CostingError("mixed_currencies", f"Movements use several currencies: {sorted(currencies)}.")
    if len(uoms) > 1:
        raise CostingError("mixed_uom", f"Movements use several units: {sorted(uoms)}; no conversion is configured.")
    return out, warnings


def _need_cost(m: Movement) -> Decimal:
    if m.unit_cost is None:
        raise CostingError("missing_cost", f"Movement {m.txn_id} ({m.txn_type}) has no unit cost.")
    if m.unit_cost < 0:
        raise CostingError("negative_cost", f"Movement {m.txn_id} has a negative unit cost.")
    return m.unit_cost


def moving_weighted_average(movements: list[Movement], *, allow_negative: bool = False) -> CostResult:
    """Moving WA: each receipt re-averages; issues and negative adjustments leave the average unchanged;
    returns and positive adjustments come back in at the current average (no value change to the average)."""
    ordered, warnings = prepare(movements)
    qty, avg = ZERO, ZERO
    with localcontext() as ctx:
        ctx.prec = 40
        for m in ordered:
            if m.quantity == 0:
                warnings.append(f"zero_quantity:{m.txn_id}")
                continue
            if m.txn_type in ADD_AT_COST:
                if m.quantity < 0:
                    raise CostingError("bad_sign", f"{m.txn_type} {m.txn_id} has a negative quantity.")
                cost = _need_cost(m)
                avg = cost if qty <= 0 else (qty * avg + m.quantity * cost) / (qty + m.quantity)
                qty += m.quantity
            else:  # ISSUE, TRANSFER_OUT, RETURN, ADJUSTMENT: move at the current average
                qty += m.quantity
                if m.txn_type in REMOVE and m.quantity > 0:
                    raise CostingError("bad_sign", f"{m.txn_type} {m.txn_id} has a positive quantity.")
            if qty < 0 and not allow_negative:
                raise CostingError("negative_stock", f"Stock goes negative at {m.txn_id} on {m.posting_date}.")
        value = qty * avg
    return CostResult(qty, avg if qty > 0 else None, value, warnings)


def periodic_weighted_average(
    movements: list[Movement], start: date, end: date, *, opening_qty: Decimal, opening_value: Decimal
) -> CostResult:
    """Period average over [start, end): (opening value + receipt value) / (opening qty + receipt qty)."""
    if end <= start:
        raise CostingError("bad_period", "The period end must be after its start.")
    ordered, warnings = prepare(movements)
    qty, value = opening_qty, opening_value
    for m in ordered:
        if not (start <= m.posting_date < end) or m.txn_type not in ADD_AT_COST:
            continue
        if m.quantity <= 0:
            continue
        qty += m.quantity
        value += m.quantity * _need_cost(m)
    if qty <= 0:
        return CostResult(qty, None, ZERO, warnings)
    return CostResult(qty, value / qty, value, warnings)


@dataclass
class Layer:
    receipt_date: date
    quantity: Decimal
    unit_cost: Decimal
    source: str


def fifo_layers(movements: list[Movement]) -> tuple[CostResult, list[Layer]]:
    """FIFO cost layers: receipts (and positive returns/adjustments with a cost) add layers, issues consume
    the oldest first. Returns the remaining layers."""
    ordered, warnings = prepare(movements)
    layers: deque[Layer] = deque()
    for m in ordered:
        if m.quantity == 0:
            warnings.append(f"zero_quantity:{m.txn_id}")
            continue
        if m.quantity > 0:
            layers.append(Layer(m.posting_date, m.quantity, _need_cost(m), m.txn_id))
            continue
        need = -m.quantity
        while need > 0:
            if not layers:
                raise CostingError("negative_stock", f"Stock goes negative at {m.txn_id} on {m.posting_date}.")
            head = layers[0]
            take = min(head.quantity, need)
            head.quantity -= take
            need -= take
            if head.quantity == 0:
                layers.popleft()
    remaining = list(layers)
    qty = sum((layer.quantity for layer in remaining), ZERO)
    value = sum((layer.quantity * layer.unit_cost for layer in remaining), ZERO)
    return CostResult(qty, (value / qty) if qty > 0 else None, value, warnings), remaining


def fifo_pick(layers: list[Layer], quantity: Decimal) -> list[tuple[Layer, Decimal]]:
    """Operational suggestion only: which layers to issue from, oldest first."""
    if quantity <= 0:
        raise CostingError("bad_quantity", "Quantity must be positive.")
    picks: list[tuple[Layer, Decimal]] = []
    need = quantity
    for layer in sorted(layers, key=lambda lay: (lay.receipt_date, lay.source)):
        if need <= 0:
            break
        take = min(layer.quantity, need)
        picks.append((layer, take))
        need -= take
    if need > 0:
        raise CostingError("insufficient_stock", "Not enough stock in the layers for this quantity.")
    return picks


@dataclass(frozen=True)
class PurchaseLine:
    po_id: str
    order_date: date
    status: str
    unit_price: Decimal | None
    receipt_date: date | None = None


def latest_valid_purchase_price(lines: list[PurchaseLine], valid_statuses: frozenset[str]) -> PurchaseLine | None:
    """Most recent purchase line (by order date, then PO id) whose status counts and which has a price."""
    candidates = [line for line in lines if line.status in valid_statuses and line.unit_price is not None]
    return max(candidates, key=lambda line: (line.order_date, line.po_id), default=None)


def latest_receipt_cost(movements: list[Movement]) -> Movement | None:
    receipts = [m for m in movements if m.txn_type == "RECEIPT" and m.unit_cost is not None and m.quantity > 0]
    return max(receipts, key=lambda m: (m.posting_date, m.txn_id), default=None)
