"""Customer Commitment Protection Mode (docs/CUSTOMER_REVENUE_PROTECTION.md, DELIVERY_FIRST_PROCUREMENT_POLICY.md).

For one confirmed customer order line:

1. Plan with MRP and trace, through pegging, the **critical materials**: planned purchases for this order whose
   earliest arrival is after the date the material is needed (the customer due date offset back through dispatch,
   manufacturing and receiving).
2. For each critical material, evaluate every supplier offer and, where one supplier lacks capacity, a split across
   suppliers. Eligibility first (approval, certificates, quality gate, quantity) — a cheaper or faster offer that is
   not eligible is never an option.
3. For each option, re-run MRP as a what-if with that sourcing (its lead time and the others at their recommended
   option), so the result is the **full material-to-customer timeline**: material arrival → production completion →
   dispatch → customer delivery. Nothing is evaluated on supplier lead time alone.
4. Recommend the cheapest option that meets the customer date (delivery-first). Show the premium against the
   cheapest offer overall and, where the order carries the data, order value, contribution margin and late-penalty
   exposure — no probabilities, no assumed losses.
5. When nothing meets the date, say so and list the fallbacks: earliest achievable delivery, partial delivery from
   stock now, renegotiating the date, approved alternates.

Recommendations only; purchasing requires an authorised human decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from lumiant.planning.calendar import add_working_days
from lumiant.planning.model import (
    HUNDRED,
    ZERO,
    DeliveryRecord,
    DemandLine,
    FxRate,
    PlanningData,
    PlanningPolicy,
    PriceRecord,
    Supplier,
    SupplierOffer,
    SupplierPolicy,
)
from lumiant.planning.mrp import LineFulfilment, MrpResult, run_mrp
from lumiant.planning.suppliers import OfferEvaluation, compare_suppliers

COMMITMENT_POLICY = SupplierPolicy(
    "customer_commitment", "cheapest", max_rejection_pct=Decimal(5), require_need_date=False
)


@dataclass
class SourcingOption:
    label: str
    kind: str  # supplier, split
    material_id: str
    suppliers: list[str]
    quantity: Decimal
    total_cost: Decimal | None  # known landed cost in base currency for the material quantity
    currency: str
    lead_days: int | None
    material_arrival: date | None
    material_needed_by: date | None
    production_complete: date | None
    customer_delivery: date | None
    meets_deadline: bool
    eligible: bool
    reasons: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    incremental_cost: Decimal | None = None  # vs the cheapest offer overall (eligible or not)
    recommended: bool = False


@dataclass
class CriticalMaterial:
    item_id: str
    warehouse_id: str
    quantity: Decimal
    needed_by: date
    planned_arrival: date | None
    reason: str


@dataclass
class Exposure:
    order_value: Decimal | None
    currency: str
    margin_value: Decimal | None
    penalty_per_day: Decimal | None
    penalty_if_cheapest: Decimal | None  # penalty × working days late under the cheapest-offer plan
    premium: Decimal | None  # recommended plan cost − cheapest-offer plan cost
    premium_pct_of_value: Decimal | None
    premium_pct_of_margin: Decimal | None
    missing: list[str]


@dataclass
class CommitmentAnalysis:
    order_key: str
    item_id: str
    customer_id: str
    quantity: Decimal
    due: date
    baseline: LineFulfilment
    at_risk: bool
    critical: list[CriticalMaterial]
    options: list[SourcingOption]
    recommended_delivery: date | None
    feasible: bool
    exposure: Exposure
    explanation: list[str]
    fallbacks: list[str]
    limitations: list[str]
    approval_required: bool = True


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    return (part / whole * HUNDRED).quantize(Decimal("0.1"), ROUND_HALF_EVEN)


def _with_lead(data: PlanningData, item_id: str, warehouse_id: str, lead: int) -> PlanningData:
    base = data.policy(item_id, warehouse_id)
    new = replace(base, warehouse_id=warehouse_id, lead_days=lead)
    kept = tuple(p for p in data.policies if not (p.item_id == item_id and p.warehouse_id == warehouse_id))
    return replace(data, policies=(*kept, new))


def _line(result: MrpResult, data: PlanningData, key: str) -> LineFulfilment | None:
    return next((ln for ln in result.fulfilment(data.calendar) if ln.key == key), None)


def analyse(
    data: PlanningData,
    order_key: str,
    *,
    offers: list[SupplierOffer],
    suppliers: dict[str, Supplier],
    deliveries: list[DeliveryRecord] | None = None,
    prices: list[PriceRecord] | None = None,
    fx: list[FxRate] | None = None,
    policy: SupplierPolicy = COMMITMENT_POLICY,
) -> CommitmentAnalysis | None:
    demand: DemandLine | None = next((d for d in data.demand if d.key == order_key), None)
    if demand is None:
        return None
    base = run_mrp(data)
    baseline = _line(base, data, order_key)
    if baseline is None:
        return None
    limitations = [
        "Production capacity is not modelled: completion dates assume the work centre is available "
        "(material feasibility only).",
        "Quoted supplier lead times are planning values, not guarantees; on-time history is shown where it exists.",
    ]
    critical: list[CriticalMaterial] = []
    for po in base.planned_orders:
        if order_key not in po.pegs or po.action != "buy":
            continue
        late = po.ready is None or po.ready > po.need
        if late:
            critical.append(
                CriticalMaterial(
                    po.item_id,
                    po.warehouse_id,
                    po.quantity,
                    po.need,
                    po.ready,
                    "lead time not maintained" if po.ready is None else f"arrives {po.ready.isoformat()}",
                )
            )
    exposure = Exposure(demand.value, demand.currency, None, demand.penalty_per_day, None, None, None, None, [])
    if demand.value is not None and demand.margin_pct is not None:
        exposure.margin_value = (demand.value * demand.margin_pct / HUNDRED).quantize(Decimal("0.01"))
    if demand.unit_price is None:
        exposure.missing.append("order unit price (order value unknown)")
    if demand.margin_pct is None:
        exposure.missing.append("contribution margin")
    if demand.penalty_per_day is None:
        exposure.missing.append("late-delivery penalty terms")

    if baseline.on_time or not critical:
        why = (
            ["The order is on time with the current plan; no delivery-first sourcing is needed."]
            if baseline.on_time
            else [
                "The order is late for reasons other than purchased materials (production lead time, a missing BOM or "
                "lead time); supplier choice cannot recover it. See the order's reasons."
            ]
        )
        return CommitmentAnalysis(
            order_key,
            demand.item_id,
            demand.customer_id,
            demand.quantity,
            demand.due,
            baseline,
            not baseline.on_time,
            critical,
            [],
            baseline.delivery,
            baseline.on_time,
            exposure,
            why,
            [],
            limitations,
        )

    # 1) Evaluate offers per critical material (eligibility, cost, arrival).
    evaluations: dict[str, list[OfferEvaluation]] = {}
    capacity = {(o.supplier_id, o.item_id): o.capacity for o in offers}
    for cm in critical:
        cmp = compare_suppliers(
            cm.item_id,
            cm.quantity,
            today=data.today,
            need_date=cm.needed_by,
            offers=offers,
            suppliers=suppliers,
            deliveries=deliveries or [],
            prices=prices or [],
            fx=fx or [],
            policy=policy,
            calendar=data.calendar,
        )
        evaluations[cm.item_id] = cmp.offers

    def candidates(cm: CriticalMaterial) -> list[SourcingOption]:
        out: list[SourcingOption] = []
        evs = evaluations[cm.item_id]
        base_pol: PlanningPolicy = data.policy(cm.item_id, cm.warehouse_id)
        extra = base_pol.receiving_days + base_pol.inspection_days
        for ev in evs:
            cap = capacity.get((ev.supplier_id, cm.item_id))
            reasons = list(ev.reasons)
            eligible = ev.eligible
            if cap is not None and cap < cm.quantity:
                eligible = False
                reasons.append(f"can supply {cap.normalize():f} of {cm.quantity.normalize():f}")
            arrival = (
                add_working_days(data.today, ev.lead_days + extra, data.calendar) if ev.lead_days is not None else None
            )
            out.append(
                SourcingOption(
                    f"{ev.supplier_name}",
                    "supplier",
                    cm.item_id,
                    [ev.supplier_id],
                    cm.quantity,
                    ev.total_cost,
                    ev.currency,
                    ev.lead_days,
                    arrival,
                    cm.needed_by,
                    None,
                    None,
                    False,
                    eligible,
                    reasons,
                    ev.notes[:3],
                )
            )
        # Split: fastest eligible-but-capacity-limited suppliers first, topped up by the next fastest eligible ones.
        pool = sorted(
            (ev for ev in evs if ev.eligible and ev.lead_days is not None and ev.total_cost is not None),
            key=lambda e: (e.lead_days, e.effective_unit_cost or ZERO),
        )
        if any((capacity.get((e.supplier_id, cm.item_id)) or cm.quantity) < cm.quantity for e in pool):
            remaining, used, cost, lead = cm.quantity, [], ZERO, 0
            for ev in pool:
                if remaining <= 0:
                    break
                cap = capacity.get((ev.supplier_id, cm.item_id))
                take = remaining if cap is None else min(cap, remaining)
                if take <= 0 or ev.unit_price is None or ev.landed_unit_cost is None:
                    continue
                used.append((ev, take))
                cost += (ev.landed_unit_cost * take).quantize(Decimal("0.01"))
                lead = max(lead, ev.lead_days or 0)
                remaining -= take
            if len(used) > 1 and remaining <= 0:
                arrival = add_working_days(data.today, lead + extra, data.calendar)
                out.append(
                    SourcingOption(
                        "Split: " + " + ".join(f"{e.supplier_name} {q.normalize():f}" for e, q in used),
                        "split",
                        cm.item_id,
                        [e.supplier_id for e, _ in used],
                        cm.quantity,
                        cost,
                        used[0][0].currency,
                        lead,
                        arrival,
                        cm.needed_by,
                        None,
                        None,
                        False,
                        True,
                        [],
                        ["arrival is the latest of the split deliveries"],
                    )
                )
        return out

    options_by_item = {cm.item_id: candidates(cm) for cm in critical}

    def pick(opts: list[SourcingOption]) -> SourcingOption | None:
        on_time = [o for o in opts if o.eligible and o.material_arrival and o.material_arrival <= o.material_needed_by]  # type: ignore[operator]
        if on_time:
            return min(
                on_time, key=lambda o: (o.total_cost if o.total_cost is not None else Decimal("1e18"), o.lead_days or 0)
            )
        timed = [o for o in opts if o.eligible and o.material_arrival]
        return min(timed, key=lambda o: o.material_arrival) if timed else None  # type: ignore[arg-type,return-value]

    chosen = {item: pick(opts) for item, opts in options_by_item.items()}

    def simulate(overrides: dict[str, int]) -> LineFulfilment | None:
        sim = data
        for cm in critical:
            if cm.item_id in overrides:
                sim = _with_lead(sim, cm.item_id, cm.warehouse_id, overrides[cm.item_id])
        return _line(run_mrp(sim), sim, order_key)

    rec_leads = {item: o.lead_days for item, o in chosen.items() if o is not None and o.lead_days is not None}
    all_options: list[SourcingOption] = []
    for cm in critical:
        # Premiums are measured against the cheapest ELIGIBLE offer: an unapproved or failing supplier's price is
        # not a real alternative, so it never makes a premium look larger or smaller.
        cheapest_any = min(
            (o.total_cost for o in options_by_item[cm.item_id] if o.total_cost is not None and o.eligible),
            default=None,
        )
        for opt in options_by_item[cm.item_id]:
            if opt.lead_days is not None:
                ln = simulate({**rec_leads, cm.item_id: opt.lead_days})
                if ln is not None:
                    opt.production_complete, opt.customer_delivery = ln.ready, ln.delivery
                    opt.meets_deadline = bool(opt.eligible and ln.on_time)
            if opt.total_cost is not None and cheapest_any is not None:
                opt.incremental_cost = opt.total_cost - cheapest_any
            opt.recommended = opt is chosen.get(cm.item_id) and opt.meets_deadline
            all_options.append(opt)

    final = simulate(rec_leads)
    feasible = bool(final and final.on_time and all(chosen.get(cm.item_id) for cm in critical))
    explanation: list[str] = []
    fallbacks: list[str] = []
    cheapest_cost = ZERO
    rec_cost = ZERO
    cheapest_lead: dict[str, int] = {}
    for cm in critical:
        opts = options_by_item[cm.item_id]
        rec = chosen.get(cm.item_id)
        priced = [o for o in opts if o.total_cost is not None and o.eligible and o.kind == "supplier"]
        cheapest = min(priced, key=lambda o: o.total_cost) if priced else None  # type: ignore[arg-type,return-value]
        cheaper_ineligible = [
            o
            for o in opts
            if not o.eligible
            and o.total_cost is not None
            and (rec is None or rec.total_cost is None or o.total_cost < rec.total_cost)
        ]
        if cheapest is not None and cheapest.total_cost is not None:
            cheapest_cost += cheapest.total_cost
            if cheapest.lead_days is not None:
                cheapest_lead[cm.item_id] = cheapest.lead_days
        if rec is not None and rec.total_cost is not None:
            rec_cost += rec.total_cost
        if rec is not None and rec.meets_deadline:
            arrives = rec.material_arrival.isoformat() if rec.material_arrival else "?"
            line = (
                f"{cm.item_id}: {rec.label} supports the customer date "
                f"(material by {cm.needed_by.isoformat()}, arrives {arrives})."
            )
            if cheapest is not None and cheapest is not rec:
                line += (
                    f" The cheapest eligible offer ({cheapest.label}) would deliver the order on "
                    + (cheapest.customer_delivery.isoformat() if cheapest.customer_delivery else "an unknown date")
                    + f", after {demand.due.isoformat()}."
                )
            elif cheapest is rec:
                line += " It is also the cheapest eligible offer."
            for o in cheaper_ineligible[:3]:
                line += f" Cheaper but excluded: {o.label} ({'; '.join(o.reasons[:1])})."
            explanation.append(line)
        else:
            explanation.append(f"{cm.item_id}: no eligible option arrives by {cm.needed_by.isoformat()}.")
    if critical:
        exposure.premium = rec_cost - cheapest_cost
        if exposure.order_value and exposure.premium is not None:
            exposure.premium_pct_of_value = _pct(exposure.premium, exposure.order_value)
        if exposure.margin_value and exposure.premium is not None:
            exposure.premium_pct_of_margin = _pct(exposure.premium, exposure.margin_value)
        cheap_line = simulate(cheapest_lead) if cheapest_lead else None
        if cheap_line is not None and demand.penalty_per_day is not None and cheap_line.late_days:
            exposure.penalty_if_cheapest = demand.penalty_per_day * cheap_line.late_days
    if feasible and exposure.premium is not None and exposure.premium > 0:
        cur = f" {exposure.currency}" if exposure.currency else ""
        msg = (
            f"Delivery-first sourcing costs {exposure.premium.normalize():f}{cur} "
            "more than the cheapest eligible offers"
        )
        if exposure.premium_pct_of_value is not None:
            msg += f", {exposure.premium_pct_of_value}% of the order value"
        if exposure.premium_pct_of_margin is not None:
            msg += f" and {exposure.premium_pct_of_margin}% of its contribution margin"
        if exposure.penalty_if_cheapest is not None:
            msg += (
                f"; the cheapest plan would incur about {exposure.penalty_if_cheapest.normalize():f} "
                "in contractual late penalties"
            )
        explanation.append(
            msg + ". Whether the premium is justified is a business decision; no purchase order is created."
        )
    if not feasible:
        earliest = min((o.customer_delivery for o in all_options if o.eligible and o.customer_delivery), default=None)
        if earliest:
            fallbacks.append(
                f"Earliest achievable delivery with eligible suppliers: {earliest.isoformat()} "
                f"(due {demand.due.isoformat()}); renegotiate the date or agree a partial delivery."
            )
        if baseline.from_stock > 0:
            fallbacks.append(
                f"Partial delivery now: {baseline.from_stock.normalize():f} of {demand.quantity.normalize():f} "
                "are available from stock."
            )
        if any(r.item_id in {cm.item_id for cm in critical} for r in data.alternates):
            fallbacks.append(
                "Approved alternates exist for a critical material; they are already used where free stock allows."
            )
        else:
            fallbacks.append(
                "No approved alternate exists for the critical materials; "
                "an engineering-approved substitute would need review."
            )
        fallbacks.append(
            "Revised production plan: prioritise this order in the allocation policy if other orders can move."
        )
    return CommitmentAnalysis(
        order_key,
        demand.item_id,
        demand.customer_id,
        demand.quantity,
        demand.due,
        baseline,
        True,
        critical,
        all_options,
        final.delivery if final else None,
        feasible,
        exposure,
        explanation,
        fallbacks,
        limitations,
    )
