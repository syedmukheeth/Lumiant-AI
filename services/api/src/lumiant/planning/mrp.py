"""Time-phased material requirements planning with pegging (docs/MRP_AND_ORDER_FULFILMENT.md).

Per item and warehouse, lowest BOM level first:

1. Supply pool: usable stock today (status unrestricted, company-owned, not expired, minus reservations and the
   protected safety stock), then open receipts on their due dates. Blocked, inspection, returns, in-transit and
   expired stock are never in the pool (scenarios 10, 11, 14).
2. Demand entries (customer orders, then dependent demand from parents' planned orders) consume the pool in the
   tenant's allocation order (due date, priority, order date … — scenario 3). Supply due on or before the need date
   covers on time; a later receipt still covers (so nothing is bought twice, scenario 62) but is reported late.
3. Approved alternates cover what is left, using only stock the alternate does not need itself (scenario 26).
4. The rest is a net requirement → planned order, lot-sized (lot-for-lot, fixed, minimum, multiple), due on the
   need date, released `lead time` working days earlier (scenarios 40, 63). Unknown lead time is a blocker, never 0.
5. Make items explode their planned orders through the BOM valid on the production date into dependent demand on
   the release date (scenarios 21–24, 28). Shared components aggregate naturally (scenario 23).
6. A last pass computes when each planned order can really be ready (today + lead times through the chain), so
   every customer line gets an honest ready date and the reason it is late (scenario 8, combined A).
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lumiant.planning.bom import explode, low_level_codes
from lumiant.planning.calendar import add_working_days, subtract_working_days, working_days_between
from lumiant.planning.model import (
    ZERO,
    AlternateRule,
    DemandLine,
    Issue,
    PlanningData,
    PlanningPolicy,
    Severity,
)
from lumiant.planning.uom import convert


@dataclass
class Coverage:
    source: str  # stock, receipt, planned, alternate
    reference: str
    item_id: str  # the item actually used (the alternate for substitutions)
    quantity: Decimal  # in units of the demanded item
    available: date | None  # None = cannot be dated (e.g. planned order without lead time)
    used_quantity: Decimal | None = None  # alternate units consumed (ratio applied)


@dataclass
class DemandEntry:
    id: str
    item_id: str
    warehouse_id: str
    quantity: Decimal
    need: date
    kind: str
    pegs: tuple[str, ...]  # top-level demand keys this entry serves
    customers: frozenset[str]
    priority: int = 5
    order_date: date | None = None
    parent_order: str | None = None
    coverage: list[Coverage] = field(default_factory=list)
    unplanned: Decimal = ZERO  # could not be planned at all (blocker)
    ready: date | None = None

    @property
    def covered(self) -> Decimal:
        return sum((c.quantity for c in self.coverage), ZERO)


@dataclass
class PlannedOrder:
    id: str
    item_id: str
    warehouse_id: str
    action: str  # make or buy
    net: Decimal
    quantity: Decimal
    need: date
    release: date | None
    lead_days: int | None
    pegs: tuple[str, ...]
    explanation: str
    bom: str | None = None
    children: list[str] = field(default_factory=list)
    ready: date | None = None
    issues: list[Issue] = field(default_factory=list)

    @property
    def excess(self) -> Decimal:
        return self.quantity - self.net


@dataclass
class ItemPosition:
    item_id: str
    warehouse_id: str
    physical: Decimal = ZERO
    usable: Decimal = ZERO
    reserved: Decimal = ZERO
    safety_stock: Decimal = ZERO
    protected: Decimal = ZERO
    not_usable: dict[str, Decimal] = field(default_factory=lambda: defaultdict(Decimal))
    scheduled: Decimal = ZERO
    gross: Decimal = ZERO
    planned: Decimal = ZERO


@dataclass
class LineFulfilment:
    key: str
    item_id: str
    warehouse_id: str
    customer_id: str
    quantity: Decimal
    due: date
    from_stock: Decimal
    from_receipts: Decimal
    from_alternates: Decimal
    from_planned: Decimal
    unplanned: Decimal
    ready: date | None
    on_time: bool
    late_days: int | None
    reasons: list[str]


@dataclass
class MrpResult:
    today: date
    entries: list[DemandEntry]
    planned_orders: list[PlannedOrder]
    positions: dict[tuple[str, str], ItemPosition]
    issues: list[Issue]
    unconsumed: dict[tuple[str, str], list[tuple[str, str, Decimal]]] = field(default_factory=dict)

    def excess_supply(self) -> list[tuple[str, str, str, str, Decimal]]:
        """Open receipts and lot-size surplus no demand consumes: potential excess (scenarios 6, combined N)."""
        return [
            (item, wh, src, ref, qty)
            for (item, wh), lots in sorted(self.unconsumed.items())
            for src, ref, qty in lots
            if src in ("receipt", "planned")
        ]

    def order(self, order_id: str) -> PlannedOrder:
        return next(p for p in self.planned_orders if p.id == order_id)

    def requirements(self) -> dict[tuple[str, str], dict[str, Decimal]]:
        """Gross, covered and planned quantity per item and warehouse."""
        out: dict[tuple[str, str], dict[str, Decimal]] = {}
        for (item, wh), pos in self.positions.items():
            if pos.gross or pos.planned:
                out[(item, wh)] = {"gross": pos.gross, "planned": pos.planned}
        return out

    def fulfilment(self, calendar_days: object | None = None) -> list[LineFulfilment]:
        from lumiant.planning.model import Calendar

        cal = calendar_days if isinstance(calendar_days, Calendar) else Calendar()
        lines = []
        for e in self.entries:
            if e.parent_order is not None or e.kind != "customer_order":
                continue
            stock = sum((c.quantity for c in e.coverage if c.source == "stock"), ZERO)
            receipts = sum((c.quantity for c in e.coverage if c.source == "receipt"), ZERO)
            alts = sum((c.quantity for c in e.coverage if c.source == "alternate"), ZERO)
            planned = sum((c.quantity for c in e.coverage if c.source == "planned"), ZERO)
            on_time = e.ready is not None and e.ready <= e.need and e.unplanned == 0
            late = (
                working_days_between(e.need, e.ready, cal) if e.ready and e.ready > e.need else (0 if e.ready else None)
            )
            lines.append(
                LineFulfilment(
                    e.pegs[0],
                    e.item_id,
                    e.warehouse_id,
                    next(iter(e.customers), ""),
                    e.quantity,
                    e.need,
                    stock,
                    receipts,
                    alts,
                    planned,
                    e.unplanned,
                    e.ready,
                    on_time,
                    late,
                    self._reasons(e),
                )
            )
        return lines

    def _reasons(self, entry: DemandEntry, depth: int = 0) -> list[str]:
        out: list[str] = []
        if depth > 12:
            return out
        if entry.unplanned:
            out.append(f"{entry.unplanned.normalize():f} of {entry.item_id} cannot be planned (see blockers).")
        for c in entry.coverage:
            if c.source == "receipt" and c.available and c.available > entry.need:
                out.append(
                    f"{c.reference} brings {c.quantity.normalize():f} {entry.item_id} on {c.available.isoformat()}, "
                    f"after the need date {entry.need.isoformat()}."
                )
            if c.source == "planned":
                po = self.order(c.reference)
                if po.ready is None:
                    out.extend(i.message for i in po.issues)
                elif po.ready > entry.need:
                    out.append(
                        f"{po.action.capitalize()} {po.quantity.normalize():f} {po.item_id}: earliest ready "
                        f"{po.ready.isoformat()} (lead time {po.lead_days} working days), "
                        f"need date {entry.need.isoformat()}."
                    )
                for child_id in po.children:
                    child = next(x for x in self.entries if x.id == child_id)
                    if child.ready is None or child.ready > (po.release or child.need):
                        out.extend(self._reasons(child, depth + 1))
        return list(dict.fromkeys(out))


# ------------------------------------------------------------------------------------------------ engine
@dataclass
class _Lot:
    quantity: Decimal
    available: date
    source: str
    reference: str


def _lot_size(net: Decimal, policy: PlanningPolicy) -> tuple[Decimal, str]:
    qty, notes = net, []
    if policy.lot_rule == "fixed" and policy.lot_size:
        qty = Decimal(math.ceil(net / policy.lot_size)) * policy.lot_size
        notes.append(f"fixed lot {policy.lot_size.normalize():f}")
    if policy.min_lot and qty < policy.min_lot:
        qty = policy.min_lot
        notes.append(f"minimum lot {policy.min_lot.normalize():f}")
    if policy.multiple and policy.multiple > 0 and qty % policy.multiple:
        qty = Decimal(math.ceil(qty / policy.multiple)) * policy.multiple
        notes.append(f"multiple of {policy.multiple.normalize():f}")
    return qty, (", ".join(notes) if notes else "lot-for-lot")


def _sort_key(e: DemandEntry, keys: tuple[str, ...]) -> tuple[object, ...]:
    parts: list[object] = [1 if e.kind == "safety_stock" else 0]
    for k in keys:
        if k == "due":
            parts.append(e.need)
        elif k == "priority":
            parts.append(e.priority)
        elif k == "order_date":
            parts.append(e.order_date or date.max)
        elif k == "quantity":
            parts.append(e.quantity)
    parts.append(e.id)
    return tuple(parts)


def run_mrp(data: PlanningData, *, substitute: bool = True) -> MrpResult:
    """Plan `data`. With `substitute`, a first pass finds stock each approved alternate does not need itself."""
    if substitute and data.alternates:
        first = _Run(data, alt_free=None).run()
        free: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for (item, wh), lots in first.leftover.items():
            free[(item, wh)] = sum((lot.quantity for lot in lots if lot.source == "stock"), ZERO)
        return _Run(data, alt_free=free).run().result
    return _Run(data, alt_free=None).run().result


class _Run:
    def __init__(self, data: PlanningData, alt_free: dict[tuple[str, str], Decimal] | None) -> None:
        self.d = data
        self.alt_free = dict(alt_free) if alt_free is not None else None
        self.issues: list[Issue] = []
        self.entries: list[DemandEntry] = []
        self.orders: list[PlannedOrder] = []
        self.pools: dict[tuple[str, str], list[_Lot]] = defaultdict(list)
        self.positions: dict[tuple[str, str], ItemPosition] = {}
        self.pending: dict[tuple[str, str], list[DemandEntry]] = defaultdict(list)
        self.leftover: dict[tuple[str, str], list[_Lot]] = {}
        self._open: dict[tuple[str, str, date], PlannedOrder] = {}
        self.llc, cycle_issues = low_level_codes(data.boms)
        self.issues += cycle_issues
        self.cyclic = {i.item_id for i in cycle_issues if i.item_id}
        self._seq = 0
        self.result: MrpResult

    # ------------------------------------------------------------------ setup
    def _id(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}-{self._seq:04d}"

    def _pos(self, item: str, wh: str) -> ItemPosition:
        key = (item, wh)
        if key not in self.positions:
            self.positions[key] = ItemPosition(item, wh)
        return self.positions[key]

    def _base_qty(self, item_id: str, qty: Decimal, uom: str, ref: str) -> Decimal | None:
        item = self.d.items.get(item_id)
        if item is None:
            self.issues.append(
                Issue(
                    "unknown_item", Severity.BLOCKER, f"{ref}: item {item_id} is not in the item master.", item_id, ref
                )
            )
            return None
        out = convert(qty, uom, item.base_uom, item_id, self.d.conversions)
        if out is None:
            self.issues.append(
                Issue(
                    "missing_uom_conversion",
                    Severity.BLOCKER,
                    f"{ref}: {qty.normalize():f} {uom} of {item_id} cannot be converted to its base unit "
                    f"{item.base_uom}; left out of the totals.",
                    item_id,
                    ref,
                )
            )
        return out

    def _setup(self) -> None:
        today = self.d.today
        reserved: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
        for r in self.d.reservations:
            reserved[(r.item_id, r.warehouse_id)] += r.quantity
        for s in self.d.stock:
            qty = self._base_qty(s.item_id, s.quantity, s.uom, f"stock {s.warehouse_id}/{s.lot_id or '-'}")
            if qty is None:
                continue
            pos = self._pos(s.item_id, s.warehouse_id)
            pos.physical += qty
            if s.usable_on(today):
                pos.usable += qty
                self.pools[(s.item_id, s.warehouse_id)].append(_Lot(qty, today, "stock", s.lot_id or "on hand"))
            else:
                reason = (
                    "expired"
                    if s.expiry and s.expiry <= today and s.status in ("unrestricted", "available")
                    else s.status
                )
                if s.owner != "company":
                    reason = f"{s.owner}-owned"
                pos.not_usable[reason] += qty
        for key, qty in reserved.items():
            pos = self._pos(*key)
            take = min(qty, pos.usable)
            pos.reserved = take
            self._take_stock(key, take)
            if qty > take:
                self.issues.append(
                    Issue(
                        "over_reserved",
                        Severity.WARNING,
                        f"Reservations of {key[0]} in {key[1]} exceed usable stock by {(qty - take).normalize():f}.",
                        key[0],
                    )
                )
        for sup in self.d.supply:
            qty = self._base_qty(sup.item_id, sup.quantity, sup.uom, sup.reference)
            if qty is None or qty <= 0:
                continue
            self._pos(sup.item_id, sup.warehouse_id).scheduled += qty
            self.pools[(sup.item_id, sup.warehouse_id)].append(_Lot(qty, sup.due, "receipt", sup.reference))
        # Safety stock is protected from customer demand; a shortfall becomes its own (last) requirement.
        for key in list(self.positions):
            policy = self.d.policy(*key)
            pos = self.positions[key]
            pos.safety_stock = policy.safety_stock
            if policy.safety_stock and self.d.allocation.protect_safety_stock:
                free = pos.usable - pos.reserved
                protect = min(policy.safety_stock, max(free, ZERO))
                pos.protected = protect
                self._take_stock(key, protect)
                if policy.safety_stock > protect:
                    self._add_entry(
                        DemandEntry(
                            self._id("SS"),
                            key[0],
                            key[1],
                            policy.safety_stock - protect,
                            today,
                            "safety_stock",
                            (f"safety stock {key[0]}",),
                            frozenset(),
                        )
                    )
        for p in self.d.policies:
            if p.safety_stock and p.warehouse_id and (p.item_id, p.warehouse_id) not in self.positions:
                self._pos(p.item_id, p.warehouse_id).safety_stock = p.safety_stock
                self._add_entry(
                    DemandEntry(
                        self._id("SS"),
                        p.item_id,
                        p.warehouse_id,
                        p.safety_stock,
                        today,
                        "safety_stock",
                        (f"safety stock {p.item_id}",),
                        frozenset(),
                    )
                )
        for dl in self.d.demand:
            self._add_demand(dl)
        for lots in self.pools.values():
            lots.sort(key=lambda lot: (lot.available, 0 if lot.source == "stock" else 1, lot.reference))

    def _take_stock(self, key: tuple[str, str], qty: Decimal) -> None:
        for lot in self.pools.get(key, []):
            if qty <= 0:
                break
            if lot.source == "stock":
                take = min(lot.quantity, qty)
                lot.quantity -= take
                qty -= take
        self.pools[key] = [lot for lot in self.pools.get(key, []) if lot.quantity > 0]

    def _add_demand(self, dl: DemandLine) -> None:
        qty = self._base_qty(dl.item_id, dl.quantity, dl.uom, f"order {dl.key}")
        if qty is None or qty <= 0:
            return
        self._add_entry(
            DemandEntry(
                dl.key,
                dl.item_id,
                dl.warehouse_id,
                qty,
                dl.due,
                dl.kind,
                (dl.key,),
                frozenset({dl.customer_id}) if dl.customer_id else frozenset(),
                dl.priority,
                dl.order_date,
            )
        )

    def _add_entry(self, e: DemandEntry) -> None:
        self.entries.append(e)
        self.pending[(e.item_id, e.warehouse_id)].append(e)
        self._pos(e.item_id, e.warehouse_id).gross += e.quantity

    # ------------------------------------------------------------------ run
    def run(self) -> _Run:
        self._setup()
        done: set[tuple[str, str]] = set()
        for _guard in range(10_000):
            open_keys = [k for k, v in self.pending.items() if v and k not in done]
            if not open_keys:
                break
            level = min(self.llc.get(k[0], 0) for k in open_keys)
            for key in sorted(k for k in open_keys if self.llc.get(k[0], 0) == level):
                self._plan_item(key)
                done.add(key)
            # Items exploded later at a deeper level re-open; a key is planned once all its parents are done.
            for k in [k for k, v in self.pending.items() if v and k in done]:
                done.discard(k)
        self.leftover = {k: [lot for lot in v if lot.quantity > 0] for k, v in self.pools.items()}
        self._ready_dates()
        unconsumed = {
            k: [(lot.source, lot.reference, lot.quantity) for lot in v] for k, v in self.leftover.items() if v
        }
        self.result = MrpResult(self.d.today, self.entries, self.orders, self.positions, self.issues, unconsumed)
        return self

    def _plan_item(self, key: tuple[str, str]) -> None:
        _item_id, _wh = key
        entries = sorted(self.pending[key], key=lambda e: _sort_key(e, self.d.allocation.keys))
        self.pending[key] = []
        pool = self.pools[key]
        for e in entries:
            remaining = e.quantity - e.covered
            remaining = self._consume(pool, e, remaining)
            if remaining > 0:
                remaining = self._substitute(e, remaining)
            if remaining > 0:
                self._plan_order(e, remaining, pool)

    def _consume(self, pool: list[_Lot], e: DemandEntry, remaining: Decimal) -> Decimal:
        # On-time supply first, then later supply (reported late) — never buy what is already on order.
        for on_time in (True, False):
            for lot in pool:
                if remaining <= 0:
                    break
                if lot.quantity <= 0 or (lot.available <= e.need) != on_time:
                    continue
                take = min(lot.quantity, remaining)
                lot.quantity -= take
                remaining -= take
                e.coverage.append(Coverage(lot.source, lot.reference, e.item_id, take, lot.available))
                if lot.source == "planned":
                    po = next(p for p in self.orders if p.id == lot.reference)
                    po.net += take  # the lot-size surplus is now promised to this demand
                    po.pegs = tuple(dict.fromkeys((*po.pegs, *e.pegs)))
        return remaining

    def _substitute(self, e: DemandEntry, remaining: Decimal) -> Decimal:
        if self.alt_free is None:
            return remaining
        rules: list[AlternateRule] = sorted(
            (r for r in self.d.alternates if r.item_id == e.item_id), key=lambda r: (r.priority, r.alternate_id)
        )
        substituted = ZERO
        for rule in rules:
            if remaining <= 0:
                break
            ok, _why = rule.usable(e.need, e.customers)
            if not ok:
                continue
            cap = remaining
            if rule.max_share_pct is not None:
                cap = min(cap, e.quantity * rule.max_share_pct / Decimal(100) - substituted)
            free_key = (rule.alternate_id, e.warehouse_id)
            free = self.alt_free.get(free_key, ZERO)
            if cap <= 0 or free <= 0 or rule.ratio <= 0:
                continue
            alt_units = min(free, cap * rule.ratio)
            covered = alt_units / rule.ratio
            self.alt_free[free_key] = free - alt_units
            self._take_stock(free_key, alt_units)
            e.coverage.append(
                Coverage(
                    "alternate",
                    f"{rule.alternate_id} (approved substitute, ratio {rule.ratio.normalize():f})",
                    rule.alternate_id,
                    covered,
                    self.d.today,
                    alt_units,
                )
            )
            remaining -= covered
            substituted += covered
        return remaining

    def _plan_order(self, e: DemandEntry, net: Decimal, pool: list[_Lot]) -> None:
        item = self.d.items.get(e.item_id)
        if item is None:
            e.unplanned += net
            return
        policy = self.d.policy(e.item_id, e.warehouse_id)
        merge_key = (e.item_id, e.warehouse_id, e.need)
        existing = self._open.get(merge_key)
        if existing is not None:
            # Same item, warehouse and date: one order, so MOQ and lot rules apply once (scenarios 23, 52).
            surplus_lot = next((lot for lot in pool if lot.source == "planned" and lot.reference == existing.id), None)
            committed = existing.quantity - (surplus_lot.quantity if surplus_lot else ZERO)  # already promised
            total = committed + net
            new_qty, lot_note = _lot_size(total, policy)
            increment = new_qty - existing.quantity
            existing.net, existing.quantity = total, new_qty
            existing.pegs = tuple(dict.fromkeys((*existing.pegs, *e.pegs)))
            existing.explanation = (
                f"net {total.normalize():f} for {len(existing.pegs)} demands; {lot_note} → {new_qty.normalize():f}"
            )
            self._pos(e.item_id, e.warehouse_id).planned += increment
            e.coverage.append(Coverage("planned", existing.id, e.item_id, net, None))
            if surplus_lot is not None:
                surplus_lot.quantity = new_qty - total
            elif new_qty > total:
                pool.append(_Lot(new_qty - total, e.need, "planned", existing.id))
            if existing.action == "make" and increment > 0:
                self._explode(existing, e.item_id, e, quantity=increment)
            return
        action = policy.procurement or ("make" if item.procurement == "make" else "buy")
        qty, lot_note = _lot_size(net, policy)
        lead = policy.lead_days
        total_lead = (
            None
            if lead is None
            else lead + (policy.receiving_days + policy.inspection_days if action == "buy" else policy.inspection_days)
        )
        release = subtract_working_days(e.need, total_lead, self.d.calendar) if total_lead is not None else None
        po = PlannedOrder(
            self._id("PLN"),
            e.item_id,
            e.warehouse_id,
            action,
            net,
            qty,
            e.need,
            release,
            total_lead,
            e.pegs,
            f"net {net.normalize():f} = demand {e.quantity.normalize():f} − covered {e.covered.normalize():f}; "
            f"{lot_note} → {qty.normalize():f}",
        )
        if total_lead is None:
            po.issues.append(
                Issue(
                    "missing_lead_time",
                    Severity.BLOCKER,
                    f"{'Production' if action == 'make' else 'Supplier'} lead time of {e.item_id} is not maintained; "
                    "its release and ready dates cannot be calculated.",
                    e.item_id,
                    po.id,
                )
            )
        elif release is not None and release < self.d.today:
            po.issues.append(
                Issue(
                    "release_overdue",
                    Severity.WARNING,
                    f"{po.action.capitalize()} {qty.normalize():f} {e.item_id} should have been released on "
                    f"{release.isoformat()} to meet {e.need.isoformat()}.",
                    e.item_id,
                    po.id,
                )
            )
        self.orders.append(po)
        self._open[merge_key] = po
        self._pos(e.item_id, e.warehouse_id).planned += qty
        e.coverage.append(Coverage("planned", po.id, e.item_id, net, None))
        if qty > net:
            pool.append(_Lot(qty - net, e.need, "planned", po.id))
            pool.sort(key=lambda lot: (lot.available, lot.reference))
        if action == "make":
            self._explode(po, item.item_id, e)

    def _explode(self, po: PlannedOrder, item_id: str, parent: DemandEntry, quantity: Decimal | None = None) -> None:
        on = po.release or po.need
        quantity = po.quantity if quantity is None else quantity
        if item_id in self.cyclic or any(c in self.cyclic for c in self._components(item_id, on)):
            po.issues.append(
                Issue(
                    "bom_cycle",
                    Severity.BLOCKER,
                    f"The BOM of {item_id} is part of a circular structure; requirements not exploded.",
                    item_id,
                    po.id,
                )
            )
            return
        ex = explode(item_id, quantity, on, self.d.boms, self.d.items, self.d.conversions, single_level=True)
        po.issues.extend(ex.issues)
        if any(
            i.severity == Severity.BLOCKER and i.code in ("missing_bom", "bom_cycle") and i.item_id == item_id
            for i in ex.issues
        ):
            return
        if ex.lines:
            po.bom = f"{ex.lines[0].bom_id} rev {ex.lines[0].revision}"
        for comp, qty in ex.totals(leaves_only=True).items():
            child = DemandEntry(
                self._id("DEP"),
                comp,
                po.warehouse_id,
                qty,
                on,
                "dependent",
                po.pegs,
                parent.customers,
                parent.priority,
                parent.order_date,
                po.id,
            )
            po.children.append(child.id)
            self._add_entry(child)

    def _components(self, item_id: str, on: date) -> list[str]:
        from lumiant.planning.bom import select_bom

        bom = select_bom(self.d.boms, item_id, on)
        return [ln.component_id for ln in bom.lines] if bom else []

    # ------------------------------------------------------------------ dates
    def _ready_dates(self) -> None:
        cal, today = self.d.calendar, self.d.today
        by_id = {p.id: p for p in self.orders}
        entries = {e.id: e for e in self.entries}

        def entry_ready(e: DemandEntry) -> date | None:
            if e.unplanned > 0:
                return None
            dates: list[date] = []
            for c in e.coverage:
                if c.source == "planned":
                    r = order_ready(by_id[c.reference])
                    if r is None:
                        return None
                    dates.append(r)
                elif c.available is not None:
                    dates.append(max(c.available, today))
            return max(dates) if dates else today

        cache: dict[str, date | None] = {}

        def order_ready(po: PlannedOrder) -> date | None:
            if po.id in cache:
                return cache[po.id]
            cache[po.id] = None  # guards against cycles
            if po.lead_days is None or any(i.severity == Severity.BLOCKER for i in po.issues):
                return None
            start = today
            if po.action == "make":
                for cid in po.children:
                    r = entry_ready(entries[cid])
                    if r is None:
                        return None
                    start = max(start, r)
            earliest = add_working_days(start, po.lead_days, cal)
            ready = max(earliest, po.need)
            cache[po.id] = ready
            po.ready = ready
            return ready

        for po in self.orders:
            order_ready(po)
        for e in self.entries:
            e.ready = entry_ready(e)
