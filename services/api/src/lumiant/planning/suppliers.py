"""Supplier evaluation before a purchase order (docs/SUPPLIER_MASTER_AND_EVALUATION.md, scenarios 46–60, 63–66).

For each supplier–item offer:

* eligibility — approved supplier and offer, supplier active, mandatory certificates valid on the need date, offer
  valid, currency convertible, enough capacity, can arrive by the need date (policy-dependent);
* comparable unit price — price break for the order quantity, ÷ price unit, converted with the latest exchange rate
  effective on the planning date (shown with its date);
* landed cost — price + freight + duty + other charges *where known*; unknown charges are listed, never assumed 0;
* order quantity — need rounded up to MOQ and order multiple; the excess is shown (scenarios 51, 52);
* evidence — rejection % and on-time % from delivery history; fewer than `min_evidence_lots` inspected deliveries
  = insufficient evidence, never an invented score (scenario 57);
* price checks — % against the last purchase price and the average over history (scenario 50).

Ranking follows the tenant's policy (weighted score, cheapest, fastest or quality first). Eligible offers always
rank above ineligible ones; offers without the evidence a weighted policy needs rank after scored ones.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from lumiant.planning.calendar import add_working_days, subtract_working_days
from lumiant.planning.model import (
    HUNDRED,
    ONE,
    ZERO,
    Calendar,
    DeliveryRecord,
    FxRate,
    PriceRecord,
    Supplier,
    SupplierOffer,
    SupplierPolicy,
)


@dataclass
class OfferEvaluation:
    supplier_id: str
    supplier_name: str
    eligible: bool
    reasons: list[str] = field(default_factory=list)  # why not eligible
    notes: list[str] = field(default_factory=list)  # assumptions and observations
    order_quantity: Decimal = ZERO
    excess_quantity: Decimal = ZERO
    unit_price: Decimal | None = None  # comparable, base currency, per base unit
    landed_unit_cost: Decimal | None = None  # known charges only
    unknown_charges: list[str] = field(default_factory=list)
    total_cost: Decimal | None = None
    effective_unit_cost: Decimal | None = None  # total cost ÷ quantity needed: MOQ excess counts against the offer
    currency: str = ""
    fx_note: str = ""
    lead_days: int | None = None
    earliest_delivery: date | None = None
    meets_need_date: bool | None = None
    latest_release: date | None = None
    rejection_pct: Decimal | None = None
    on_time_pct: Decimal | None = None
    evidence_lots: int = 0
    price_vs_last_pct: Decimal | None = None
    price_vs_average_pct: Decimal | None = None
    score: Decimal | None = None
    rank: int | None = None
    allocated: Decimal = ZERO  # for split sourcing


@dataclass
class SupplierComparison:
    item_id: str
    quantity: Decimal
    need_date: date | None
    policy: str
    offers: list[OfferEvaluation]
    split: list[OfferEvaluation]
    recommendation: str
    gaps: list[str]

    @property
    def best(self) -> OfferEvaluation | None:
        return next((o for o in self.offers if o.eligible and o.rank == 1), None)


def _pct(new: Decimal, old: Decimal) -> Decimal:
    return ((new - old) / old * HUNDRED).quantize(Decimal("0.1"), ROUND_HALF_EVEN)


def fx_rate(rates: tuple[FxRate, ...] | list[FxRate], src: str, dst: str, on: date) -> FxRate | None:
    """Latest rate effective on `on` (direct or inverse). Same currency → rate 1."""
    if src == dst:
        return FxRate(src, dst, ONE, on)
    best: FxRate | None = None
    for r in rates:
        if r.valid_from > on:
            continue
        if r.from_currency == src and r.to_currency == dst:
            cand = r
        elif r.from_currency == dst and r.to_currency == src and r.rate:
            cand = FxRate(src, dst, ONE / r.rate, r.valid_from)
        else:
            continue
        if best is None or cand.valid_from > best.valid_from:
            best = cand
    return best


def _order_quantity(need: Decimal, offer: SupplierOffer) -> Decimal:
    qty = max(need, offer.moq)
    if offer.multiple and offer.multiple > 0 and qty % offer.multiple:
        qty = Decimal(math.ceil(qty / offer.multiple)) * offer.multiple
    return qty


def _unit_price(offer: SupplierOffer, qty: Decimal) -> tuple[Decimal, str]:
    price, note = offer.price, ""
    for br in sorted(offer.price_breaks, key=lambda b: b.min_quantity):
        if qty >= br.min_quantity:
            price, note = br.price, f"price break from {br.min_quantity.normalize():f}"
    return price / offer.price_unit, note


def supplier_evidence(
    records: list[DeliveryRecord], policy: SupplierPolicy
) -> tuple[Decimal | None, Decimal | None, int]:
    received = [r for r in records if r.received is not None and r.quantity_received > 0]
    lots = len(received)
    if lots < policy.min_evidence_lots:
        return None, None, lots
    qty = sum((r.quantity_received for r in received), ZERO)
    rejected = sum((r.quantity_rejected for r in received), ZERO)
    rejection = (rejected / qty * HUNDRED).quantize(Decimal("0.1"), ROUND_HALF_EVEN) if qty else None
    on_time = sum(1 for r in received if r.received and r.received <= r.promised)
    return rejection, (Decimal(on_time) / Decimal(lots) * HUNDRED).quantize(Decimal("0.1"), ROUND_HALF_EVEN), lots


def compare_suppliers(
    item_id: str,
    quantity: Decimal,
    *,
    today: date,
    need_date: date | None,
    offers: list[SupplierOffer],
    suppliers: dict[str, Supplier],
    deliveries: list[DeliveryRecord] = [],  # noqa: B006 — read only
    prices: list[PriceRecord] = [],  # noqa: B006
    fx: list[FxRate] = [],  # noqa: B006
    policy: SupplierPolicy | None = None,
    calendar: Calendar | None = None,
    receiving_days: int = 0,
    inspection_days: int = 0,
) -> SupplierComparison:
    policy = policy or SupplierPolicy()
    calendar = calendar or Calendar()
    gaps: list[str] = []
    item_offers = [o for o in offers if o.item_id == item_id]
    evals: list[OfferEvaluation] = []
    base = policy.base_currency
    for o in item_offers:
        sup = suppliers.get(o.supplier_id)
        ev = OfferEvaluation(o.supplier_id, sup.name if sup else o.supplier_id, True, currency=base)
        if sup is None:
            ev.eligible = False
            ev.reasons.append("supplier is not in the supplier master")
        else:
            if not sup.approved:
                ev.eligible = False
                ev.reasons.append("supplier is not approved")
            if sup.status != "active":
                ev.eligible = False
                ev.reasons.append(f"supplier status is {sup.status}")
            check_day = need_date or today
            for cert in sup.certifications:
                if cert.mandatory and cert.expires is not None and cert.expires < check_day:
                    msg = f"mandatory certificate {cert.name} expired on {cert.expires.isoformat()}"
                    if policy.require_mandatory_certifications:
                        ev.eligible = False
                        ev.reasons.append(msg)
                    else:
                        ev.notes.append(msg + " (allowed by policy exception)")
        if not o.approved:
            ev.eligible = False
            ev.reasons.append("this supplier–item relationship is not approved")
        if (o.valid_to and o.valid_to < today) or (o.valid_from and o.valid_from > today):
            ev.eligible = False
            ev.reasons.append("quotation is not valid today")
        ev.order_quantity = _order_quantity(quantity, o)
        ev.excess_quantity = ev.order_quantity - quantity
        if ev.excess_quantity:
            ev.notes.append(
                f"order {ev.order_quantity.normalize():f} (MOQ {o.moq.normalize():f}"
                + (f", multiple {o.multiple.normalize():f}" if o.multiple else "")
                + f") for a need of {quantity.normalize():f}: {ev.excess_quantity.normalize():f} more than needed"
            )
        if o.capacity is not None and o.capacity < quantity:
            ev.notes.append(f"capacity {o.capacity.normalize():f} is below the need; can cover part only")
        price, break_note = _unit_price(o, ev.order_quantity)
        if break_note:
            ev.notes.append(break_note)
        rate = fx_rate(fx, o.currency, base, today)
        if rate is None:
            ev.eligible = False
            ev.reasons.append(
                f"no approved {o.currency}→{base} exchange rate effective {today.isoformat()}; prices not comparable"
            )
        else:
            if o.currency != base:
                ev.fx_note = (
                    f"1 {o.currency} = {rate.rate.normalize():f} {base} (rate from {rate.valid_from.isoformat()})"
                )
            ev.unit_price = (price * rate.rate).quantize(Decimal("0.0001"), ROUND_HALF_EVEN)
            landed = price
            if o.freight is None:
                ev.unknown_charges.append("freight")
            else:
                landed += o.freight
            if o.duty_pct is None:
                ev.unknown_charges.append("duty")
            else:
                landed += price * o.duty_pct / HUNDRED
            if o.other_charges is not None:
                landed += o.other_charges
            ev.landed_unit_cost = (landed * rate.rate).quantize(Decimal("0.0001"), ROUND_HALF_EVEN)
            ev.total_cost = (ev.landed_unit_cost * ev.order_quantity).quantize(Decimal("0.01"), ROUND_HALF_EVEN)
            if quantity > 0:
                ev.effective_unit_cost = (ev.total_cost / quantity).quantize(Decimal("0.0001"), ROUND_HALF_EVEN)
            if ev.unknown_charges:
                ev.notes.append(
                    "landed cost excludes unknown " + " and ".join(ev.unknown_charges) + " (not assumed zero)"
                )
        ev.lead_days = o.lead_days
        if o.lead_days is None:
            ev.notes.append("supplier lead time for this item is not maintained")
            if need_date and policy.require_need_date:
                ev.eligible = False
                ev.reasons.append("delivery date cannot be checked: no lead time")
        else:
            total = o.lead_days + receiving_days + inspection_days
            ev.earliest_delivery = add_working_days(today, total, calendar)
            if need_date:
                ev.meets_need_date = ev.earliest_delivery <= need_date
                ev.latest_release = subtract_working_days(need_date, total, calendar)
                if not ev.meets_need_date and policy.require_need_date:
                    ev.eligible = False
                    ev.reasons.append(
                        f"earliest delivery {ev.earliest_delivery.isoformat()} is after the need date "
                        f"{need_date.isoformat()}"
                    )
        hist = [d for d in deliveries if d.supplier_id == o.supplier_id and d.item_id == item_id]
        ev.rejection_pct, ev.on_time_pct, ev.evidence_lots = supplier_evidence(hist, policy)
        if ev.rejection_pct is None:
            ev.notes.append(
                f"insufficient quality and delivery evidence ({ev.evidence_lots} received deliveries, "
                f"{policy.min_evidence_lots} needed)"
            )
        elif policy.max_rejection_pct is not None and ev.rejection_pct > policy.max_rejection_pct:
            ev.eligible = False
            ev.reasons.append(
                f"rejection rate {ev.rejection_pct}% exceeds the {policy.max_rejection_pct}% quality limit"
            )
        if (
            ev.on_time_pct is not None
            and policy.min_on_time_pct is not None
            and ev.on_time_pct < policy.min_on_time_pct
        ):
            ev.eligible = False
            ev.reasons.append(f"on-time delivery {ev.on_time_pct}% is below the {policy.min_on_time_pct}% minimum")
        if ev.unit_price is not None:
            ph = sorted((p for p in prices if p.item_id == item_id and p.kind == "purchase"), key=lambda p: p.day)
            conv = [(p, fx_rate(fx, p.currency, base, p.day)) for p in ph]
            conv_prices = [p.price * r.rate for p, r in conv if r is not None]
            if conv_prices:
                last = conv_prices[-1]
                avg = sum(conv_prices, ZERO) / len(conv_prices)
                ev.price_vs_last_pct = _pct(ev.unit_price, last)
                ev.price_vs_average_pct = _pct(ev.unit_price, avg)
                ev.notes.append(
                    f"{ev.price_vs_last_pct:+}% vs last purchase price ({ph[-1].day.isoformat()}), "
                    f"{ev.price_vs_average_pct:+}% vs the average of {len(conv_prices)} purchases "
                    f"since {ph[0].day.isoformat()}"
                )
        evals.append(ev)

    _rank(evals, policy)
    split = _split(evals, item_offers, quantity)
    if not item_offers:
        gaps.append(f"No supplier–item relationship exists for {item_id}: sourcing gap, needs procurement review.")
    elif not any(e.eligible for e in evals):
        gaps.append(
            f"No approved, eligible supplier for {item_id} under the '{policy.name}' policy; "
            "procurement or compliance review needed."
        )
    rec = _recommend(item_id, evals, split, policy, quantity)
    return SupplierComparison(item_id, quantity, need_date, policy.name, evals, split, rec, gaps)


def _rank(evals: list[OfferEvaluation], policy: SupplierPolicy) -> None:
    eligible = [e for e in evals if e.eligible]
    prices = [e.effective_unit_cost for e in eligible if e.effective_unit_cost is not None]
    leads = [e.lead_days for e in eligible if e.lead_days is not None]
    min_price = min(prices) if prices else None
    min_lead = min(leads) if leads else None
    for e in eligible:
        if policy.mode != "weighted":
            continue
        parts: dict[str, Decimal | None] = {
            "price": (min_price / e.effective_unit_cost) if min_price and e.effective_unit_cost else None,
            "quality": (ONE - e.rejection_pct / HUNDRED) if e.rejection_pct is not None else None,
            "delivery": (e.on_time_pct / HUNDRED) if e.on_time_pct is not None else None,
            "lead_time": (Decimal(max(min_lead, 1)) / Decimal(max(e.lead_days, 1)))
            if min_lead is not None and e.lead_days is not None
            else None,
        }
        missing = [k for k, w in policy.weights.items() if w and parts.get(k) is None]
        if missing:
            e.notes.append("not scored: no evidence for " + ", ".join(missing))
            continue
        e.score = sum(
            (policy.weights[k] * (parts[k] or ZERO) for k in policy.weights if policy.weights[k]), ZERO
        ).quantize(Decimal("0.001"), ROUND_HALF_EVEN)

    def key(e: OfferEvaluation) -> tuple[object, ...]:
        big = Decimal("1e18")
        cost = e.effective_unit_cost or big
        if policy.mode == "cheapest":
            return (0 if e.eligible else 1, cost, e.lead_days or 10**6, e.supplier_id)
        if policy.mode == "fastest":
            return (0 if e.eligible else 1, e.earliest_delivery or date.max, cost, e.supplier_id)
        if policy.mode == "quality":
            rej = e.rejection_pct if e.rejection_pct is not None else big
            return (0 if e.eligible else 1, rej, cost, e.supplier_id)
        return (0 if e.eligible else 1, 0 if e.score is not None else 1, -(e.score or ZERO), cost, e.supplier_id)

    evals.sort(key=key)
    for i, e in enumerate(evals, 1):
        e.rank = i if e.eligible else None


def _split(evals: list[OfferEvaluation], offers: list[SupplierOffer], quantity: Decimal) -> list[OfferEvaluation]:
    """Split across eligible suppliers in rank order when no single one has the capacity (scenarios 55, 64)."""
    caps = {o.supplier_id: o.capacity for o in offers}
    eligible = [e for e in evals if e.eligible]
    first_cap = caps.get(eligible[0].supplier_id) if eligible else None
    if not eligible or first_cap is None or first_cap >= quantity:
        return []
    remaining, out = quantity, []
    for e in eligible:
        if remaining <= 0:
            break
        cap = caps.get(e.supplier_id)
        take = remaining if cap is None else min(cap, remaining)
        if take > 0:
            e.allocated = take
            out.append(e)
            remaining -= take
    if remaining > 0:
        out.append(
            OfferEvaluation(
                "-",
                "uncovered",
                False,
                reasons=[f"{remaining.normalize():f} not covered by any eligible supplier"],
                allocated=remaining,
            )
        )
    return out


def _recommend(
    item_id: str, evals: list[OfferEvaluation], split: list[OfferEvaluation], policy: SupplierPolicy, qty: Decimal
) -> str:
    best = next((e for e in evals if e.eligible and e.rank == 1), None)
    if best is None:
        return (
            f"No eligible supplier for {item_id}; do not raise a purchase order until procurement "
            "reviews the sourcing gap."
        )
    if split:
        parts = ", ".join(f"{e.supplier_name} {e.allocated.normalize():f}" for e in split if e.supplier_id != "-")
        return (
            f"No single eligible supplier can supply {qty.normalize():f}; consider splitting: {parts}. "
            "Recommendation only: no order is created."
        )
    why = {
        "weighted": f"best weighted score {best.score}"
        if best.score is not None
        else "the only offer with complete evidence",
        "cheapest": "lowest known landed cost per unit needed among eligible offers",
        "fastest": "earliest delivery among eligible offers",
        "quality": "lowest rejection rate among eligible offers",
    }[policy.mode]
    return (
        f"Under the '{policy.name}' policy, {best.supplier_name} ranks first ({why}). "
        "This is a recommendation for review; no purchase order is created or approved."
    )
