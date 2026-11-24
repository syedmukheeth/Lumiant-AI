"""Obsolescence and lifecycle review (scenarios 19, 20, 74–79, combined F and K).

An item is never called obsolete from inactivity alone. It becomes an *obsolete candidate* only when it has no
movement for the threshold, no open demand, no use in any released BOM valid today or for an open order's date,
is not marked critical, and has stock. Critical spares are kept; superseded items show how much of the old stock
open demand still needs. Every verdict lists its evidence and needs review by an authorised user.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lumiant.planning.bom import where_used
from lumiant.planning.model import ZERO, Bom, Item
from lumiant.planning.mrp import MrpResult


@dataclass
class LifecycleFinding:
    item_id: str
    verdict: str  # active, slow_moving_review, obsolete_candidate, critical_keep, superseded_run_down, expiring_action
    on_hand: Decimal
    evidence: list[str] = field(default_factory=list)
    still_needed: Decimal | None = None
    possible_excess: Decimal | None = None
    action: str = ""


def review(
    items: dict[str, Item],
    on_hand: dict[str, Decimal],
    last_movement: dict[str, date | None],
    *,
    today: date,
    boms: tuple[Bom, ...] | list[Bom],
    mrp: MrpResult | None = None,
    dormant_days: int = 365,
    slow_days: int = 180,
    expiring: dict[str, tuple[date, Decimal]] | None = None,
) -> list[LifecycleFinding]:
    gross: dict[str, Decimal] = {}
    order_dates: list[date] = []
    if mrp is not None:
        for e in mrp.entries:
            gross[e.item_id] = gross.get(e.item_id, ZERO) + e.quantity
            order_dates.append(e.need)
    out: list[LifecycleFinding] = []
    for item_id, item in sorted(items.items()):
        stock = on_hand.get(item_id, ZERO)
        if stock <= 0:
            continue
        last = last_movement.get(item_id)
        idle = (today - last).days if last else None
        demand = gross.get(item_id, ZERO)
        dates = [today, *order_dates]
        used_in = {f"{b.item_id} ({b.bom_id} rev {b.revision})" for d in dates for b in where_used(boms, item_id, d)}
        ev = [f"{stock.normalize():f} on hand"]
        ev.append(f"last movement {last.isoformat()} ({idle} days ago)" if last else "no movement on record")
        if demand:
            ev.append(f"open demand {demand.normalize():f}")
        if used_in:
            ev.append("used in active BOMs: " + ", ".join(sorted(used_in)[:5]))
        if expiring and item_id in expiring:
            exp_day, exp_qty = expiring[item_id]
            ev.append(f"{exp_qty.normalize():f} expires on {exp_day.isoformat()}")
            usable_need = min(demand, exp_qty)
            out.append(
                LifecycleFinding(
                    item_id,
                    "expiring_action",
                    stock,
                    ev,
                    usable_need,
                    exp_qty - usable_need,
                    "Use or transfer before expiry where quality allows; review the remainder.",
                )
            )
            continue
        if item.lifecycle == "superseded" or item.superseded_by:
            excess = max(stock - demand, ZERO)
            ev.append(f"superseded by {item.superseded_by or 'a newer item'}")
            out.append(
                LifecycleFinding(
                    item_id,
                    "superseded_run_down",
                    stock,
                    ev,
                    min(stock, demand),
                    excess,
                    "Use the old item for demand that still needs it; stop buying it; review the excess.",
                )
            )
            continue
        if item.critical:
            ev.append("marked critical (e.g. maintenance spare)")
            out.append(
                LifecycleFinding(
                    item_id,
                    "critical_keep",
                    stock,
                    ev,
                    None,
                    None,
                    "Keep: low movement does not make a critical spare obsolete; review stock level only.",
                )
            )
            continue
        if demand or used_in:
            out.append(LifecycleFinding(item_id, "active", stock, ev, demand or None, None, "No lifecycle action."))
            continue
        if idle is None or idle >= dormant_days:
            out.append(
                LifecycleFinding(
                    item_id,
                    "obsolete_candidate",
                    stock,
                    ev,
                    ZERO,
                    stock,
                    "Candidate for review: restrict new purchases; an authorised user decides on disposal.",
                )
            )
        elif idle >= slow_days:
            out.append(
                LifecycleFinding(
                    item_id, "slow_moving_review", stock, ev, ZERO, None, "Review purchasing and stock level."
                )
            )
    return out
