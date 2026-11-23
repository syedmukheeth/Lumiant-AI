# Customer Revenue Protection (Customer Commitment Protection Mode)

_23 Nov 2026. Code: `services/api/src/lumiant/planning/commitment.py`. Policy: `DELIVERY_FIRST_PROCUREMENT_POLICY.md`._

## The question it answers

> "This customer order will be late on the current plan. Is there a supplier, or a split between suppliers, that still meets the customer's date? What does it cost against the cheapest eligible option, and how much revenue, margin and penalty is at stake?"

Cheapest-first purchasing can lose a high-value order to save a small amount on one component. This mode runs **only for late or undatable order lines**. For every critical material it compares the eligible sourcing options **on the full delivery timeline**, not on supplier lead time alone.

## Timeline per option

```
supplier lead time + receiving + inspection   → material arrival
material arrival + production lead time       → production completion   (whole BOM; other components still constrain)
production completion + shipping days         → customer delivery       (compared with the customer due date)
```

- Every date is in working days on the tenant's calendar (a Fri/Sat weekend for demo-delta).
- Each option is a real **MRP what-if rerun**: the option's lead time replaces the planning default for that material, then the whole plan is replanned.
- So the result includes every other constraint as well: shared components, other orders competing for the same stock, and alternates.
- The option is not judged by a separate shortcut formula.
- `ship_days` is a field on the customer order line. A line with `ship_days` is planned to be ready by `due − ship_days`.

## What is shown (`GET /api/planning/commitment?order=SO-1001/10`)

| Block | Content |
|---|---|
| Baseline | Current plan: ready date, delivery date, working days late, reasons |
| Critical materials | Buy orders pegged to this line that arrive after their need date, or that cannot be dated |
| Options table | Option, Material arrival (vs needed by), Production completion, Customer delivery (vs deadline), Total cost, vs cheapest eligible, Feasibility |
| Recommendation | The cheapest **eligible** option that meets the customer date, or a split when no single supplier has the quantity |
| Exposure | Order value, margin value, penalty per day, penalty if the cheapest option is chosen, premium in currency and as a % of value and of margin |
| Fallbacks (infeasible) | Earliest achievable date, partial delivery from stock now, alternate or substitute review |
| Limitations | Production capacity is not modelled; quoted lead times are planning values, not guarantees |

## No invented numbers

- Order value appears only when the order line has `unit_price`. Margin needs `margin_pct`, and penalties need `penalty_per_day`. Anything missing is listed under `exposure.missing` and never estimated.
- **No probabilities are invented.** Lumiant does not show a "% chance of losing the customer". Supplier on-time history is shown where at least 3 deliveries exist, and is labelled as evidence.
- `penalty_if_cheapest` = penalty per day × the working days the cheapest eligible option would be late. It is shown only when a penalty rate exists.
- Premiums are measured against the **cheapest eligible** offer. An unapproved, uncertified, failing or unpriced supplier is shown with its reason, together with "Cheaper but excluded: …". It never shrinks or inflates the premium, and it is never recommended.

## Combined scenarios

| Id | Situation | Result | Check |
|---|---|---|---|
| P | High-value order; the cheap supplier is too slow, the fast one costs more | Fast supplier recommended. Premium 4,000 SAR (0.8% of value, 4.0% of margin) against about 26,000 SAR of penalties | `C-P` |
| P2 | Fast supplier fails the 5% rejection gate | Fast supplier not eligible, order infeasible, fallbacks given | `C-P2` |
| P3 | Material in stock, order already on time | No options, no premium proposed | `C-P3` |
| Q | Fastest supplier lacks quantity | Split (60 + 40) at 14,400, cheaper than the single fast supplier at 15,000 | `C-Q` |
| R | No option meets the date | Infeasible. Earliest achievable date, partial delivery of 30 of 100 from stock now, alternate review | `C-R` |
| demo-delta | SO-1001/10, 30 pumps, 555,000 SAR | Beta Castings meets the date and is also the cheapest eligible offer. Alpha, Omega, Zeta and Gamma are each excluded with their reason | `int:test_commitment_protection_on_the_pump_order` |

## Access, audit and safety

- Requires `cost:read` (service, API and assistant). Without it: HTTP 403, and the assistant refuses without leaking values.
  - `int:test_commitment_needs_cost_access_and_a_known_order`, `int:test_commitment_api`, `int:test_assistant_commitment_answer_is_grounded_and_cost_gated`.
- Warehouse scope applies, because the analysis reruns the scoped plan.
- Every analysis is recorded in the audit log as `planning:commitment`.
- Rate limit: the `planning` bucket (30/min/user).
- **Recommendation only, `approval_required: true`.** No purchase order is created, no supplier is contacted, no customer date is changed.

## Where it appears

- **Web:** Procure → **Commitment protection** (`/commitments`). The at-risk list is sorted by order value, and each line opens its analysis. Late lines in Orders & materials offer **Protect this order**.
- **Assistant:** the `customer_commitment` tool. Routed for "is it worth paying more", "protect this order/customer", "revenue at risk", "cheapest vs fastest", "penalty". Grounded: every number in the answer comes from the tool data.

## Not modelled yet (honest limits)

- Production capacity and re-sequencing: a completion date assumes the work centre is free. The same is true for expediting production itself.
- Freight-mode upgrades (air vs sea) are modelled only when they exist as separate supplier offers with their own lead time and freight.
- Customer-specific service levels beyond `priority`, and contractual penalty caps.

## Natural-language questions (built-in assistant, no paid model)

The rule-based assistant recognises everyday wording, not only fixed phrases. It resolves the order by id (`SO-1002`), or by the customer or product named ("the CUST-HARBOR order", "the pump order"). When nothing is named, it takes the highest-value order at risk and says so. Examples routed to `customer_commitment` and tested:

- "Can we still deliver SO-1001 on time if we use a faster supplier?"
- "Which orders are we going to miss and how much money is at stake?"
- "How do we save the CUST-OASIS order?"
- "Cheaper supplier or faster supplier for the pump order?"
- "Can we split the impeller order between suppliers to meet the date?"

A quote request with a stated quantity ("fastest supplier for 27 units of RM-IMPELLER") stays a supplier comparison. A plain status question ("When will SO-1001 ship?") stays order fulfilment. The full regression set is `test_assistant_routes_planning_questions` (30 phrasings). Wording outside these patterns is answered with "I can't answer that yet" rather than a guess. Free-form understanding of any wording needs the optional LLM provider, which is off by default because it would cost money.
