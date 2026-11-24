# Delivery-First Procurement Policy

_23 Nov 2026. Applies to Customer Commitment Protection (`CUSTOMER_REVENUE_PROTECTION.md`). Code: `COMMITMENT_POLICY` in `services/api/src/lumiant/planning/commitment.py`._

## Rule

When a customer order line would be late, choose **the cheapest eligible sourcing option that still meets the customer date**. Only when none meets it, show the earliest eligible option and the fallbacks.

Speed is a constraint, not a score. Among the options that meet the date, cost decides. A faster option that costs more is not preferred when a cheaper one also meets the date.

## Eligibility gates (never traded off against speed or price)

| Gate | Default | Source |
|---|---|---|
| Supplier approved for the item | required | supplier master / approved supplier list |
| Mandatory certificates valid on the planning date | required | supplier certificates |
| Rejection rate on received deliveries | at most 5% (stricter than the balanced policy) | delivery history (at least 3 deliveries; less is "insufficient evidence", not a failure) |
| Price comparable | an approved FX rate for the quote currency | FX table |
| Capacity | the offer can supply the full quantity, otherwise it is split-only | offer capacity |

A supplier that fails a gate still appears in the table with the reason. It is never recommended, and it is not used as the "cheapest" baseline for premiums.

## Split sourcing

- When no single eligible supplier can supply the full quantity in time, a split is built from the fastest eligible offers, filling capacity in order.
- The split is recommended only if it meets the date and is the cheapest option that does.
- Example `C-Q`: 60 + 40 at 14,400 beats a single supplier at 15,000.

## Premium reporting

- `incremental_cost` per option = its total cost − the cheapest eligible option's total cost.
- `premium` for the recommendation is reported in currency, as a % of order value and as a % of margin, where those exist.
- When the order has a penalty rate, the penalty the cheapest option would incur is shown next to the premium. A buyer can then weigh the two from figures, not opinions.

## Who decides

- Lumiant recommends. A buyer or procurement manager with `cost:read` approves (`approval_required: true`).
- Nothing is ordered, no supplier is contacted and no customer date is changed by the platform.
- Thresholds are code defaults today. Making them editable per tenant is on the roadmap (`IMPLEMENTATION_ROADMAP.md`).

## Tests

- Scenario harness `evals/scenarios/05_customer_commitment.yaml` (C-P, C-P2, C-P3, C-Q, C-R).
- Integration tests on demo-delta in `tests/integration/test_planning.py` (commitment tests).
