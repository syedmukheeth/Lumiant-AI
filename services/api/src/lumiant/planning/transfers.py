"""Inter-warehouse balancing (scenarios 12, 13, combined D and O): transfer surplus before buying more.

Surplus at a source = usable stock − its own demand − its safety stock (from an MRP run, so nothing promised
elsewhere is moved). A transfer is feasible when an allowed lane exists; it is compared with buying by arrival date
and, where both are known, by cost. Missing transfer cost is reported, not assumed zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lumiant.planning.calendar import add_working_days
from lumiant.planning.model import ZERO, Calendar
from lumiant.planning.mrp import MrpResult


@dataclass(frozen=True)
class TransferLane:
    source: str
    destination: str
    lead_days: int
    cost_per_unit: Decimal | None = None
    allowed: bool = True
    note: str = ""


@dataclass
class TransferOption:
    item_id: str
    source: str
    destination: str
    quantity: Decimal
    arrival: date
    cost: Decimal | None
    notes: list[str] = field(default_factory=list)


def surplus(result: MrpResult) -> dict[tuple[str, str], Decimal]:
    """Usable stock left after every demand and safety stock of the same warehouse (only on-hand, not receipts)."""
    out: dict[tuple[str, str], Decimal] = {}
    for key, lots in result.unconsumed.items():
        qty = sum((q for src, _ref, q in lots if src == "stock"), ZERO)
        if qty > 0:
            out[key] = qty
    return out


def transfer_options(
    result: MrpResult,
    item_id: str,
    destination: str,
    shortage: Decimal,
    lanes: list[TransferLane],
    calendar: Calendar | None = None,
) -> list[TransferOption]:
    calendar = calendar or Calendar()
    options: list[TransferOption] = []
    remaining = shortage
    spare = surplus(result)
    for lane in sorted((ln for ln in lanes if ln.destination == destination), key=lambda ln: (ln.lead_days, ln.source)):
        if remaining <= 0:
            break
        avail = spare.get((item_id, lane.source), ZERO)
        if avail <= 0:
            continue
        notes = []
        if not lane.allowed:
            notes.append(
                f"transfers {lane.source} → {destination} are not allowed{': ' + lane.note if lane.note else ''}"
            )
            options.append(TransferOption(item_id, lane.source, destination, ZERO, result.today, None, notes))
            continue
        qty = min(avail, remaining)
        cost = None if lane.cost_per_unit is None else (lane.cost_per_unit * qty).quantize(Decimal("0.01"))
        if cost is None:
            notes.append("transfer cost is not maintained (not assumed zero)")
        arrival = add_working_days(result.today, lane.lead_days, calendar)
        options.append(TransferOption(item_id, lane.source, destination, qty, arrival, cost, notes))
        remaining -= qty
    return options
