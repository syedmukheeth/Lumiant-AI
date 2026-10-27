# Inventory Calculations

> **Status: definitions pending customer approval (D-002).** Do not present anything here as a customer's accounting policy until they approve it. Synthetic tenants use these definitions only for demonstration.

## Rules for every calculation

| Rule | Detail |
|---|---|
| Arithmetic | Python `Decimal`; DB `DECIMAL(18,4)`. Never float. |
| Rounding | Keep intermediates unrounded. Round only for display: money 2 dp, quantity 3 dp, unit cost 4 dp, `ROUND_HALF_EVEN` unless the customer specifies otherwise. |
| Currency | Never aggregate across currencies without an approved FX table (none exists yet). |
| UoM | Never aggregate across units without an approved conversion table (none exists yet). |
| Time | Posting date decides the period; periods are `[start, end)`; UTC until Q-016 is answered. |
| Missing data | Return "not computable" and name the missing field. Never guess, never substitute zero. |
| Provenance | Every output carries a rule id and version. |

## M1 — implemented

### Inventory value (`inventory_value_*` v1)
`Σ(on-hand quantity × source valuation price)`, per currency, within the user's scope.
- The valuation price is taken **as the source provides it** (`stock_balance.valuation_price`, e.g. an ERP moving average). M1 does not recompute it.
- Lines with no valuation price are left out of the value and **counted** in a `missing_valuation_price` warning.

### Below reorder (`below_reorder` v1)
For every item–warehouse in scope that has a customer reorder policy: `on_hand = Σ quantity` (0 when there are no stock lines). Flag it when `on_hand < reorder_level`.
- Items without a policy are **not** flagged; they are counted as `no_policy`.
- Each row explains itself: on-hand, reorder level, shortfall, UoM.

## M2 — implemented as DRAFT definitions (`services/api/src/lumiant/costing/`, hand-computed tests in `tests/unit/test_costing.py`)

Still pending customer approval (D-002). Implemented: moving WA, periodic WA, FIFO layers + pick suggestion, lot cost display, both latest-price definitions, computed ABC (value = on-hand value; cutoffs supplied per request), item-code rules, excess/dormant/expiry/data-quality analyses. Not yet: LIFO (operational rule only, needs customer configuration), ageing buckets, price-movement alerts, periodic average UI.

### Original design notes

| Method | Definition | Open question |
|---|---|---|
| Moving weighted average | On each receipt: `(qty_before×avg_before + qty_r×cost_r)/(qty_before+qty_r)`. Issues don't change it. | Negative stock, returns, transfers (Q-006) |
| Periodic weighted average | `(opening value + Σ receipt value)/(opening qty + Σ receipt qty)` per period | Period calendar (Q-007) |
| FIFO cost layers | Receipts add layers; issues consume the oldest first | Needs authoritative receipt dates |
| FIFO pick suggestion | Oldest eligible lots first; excludes expired/blocked; output is a recommendation only | — |
| LIFO | Operational issue rule only, if configured; **never** valuation unless the policy says so (F-009) | — |
| Lot cost | `lot.unit_cost` at receipt, compared with MWA on that date | — |
| Latest price | Choose per tenant: `latest_valid_purchase_price` or `latest_receipt_cost` | Q-008 |
| Computed ABC | Configurable value definition, period and thresholds; no defaults without configuration | Q-005 |

## Fixtures needed before M2 counts as verified
Hand-computed expected results for: zero quantities, negative adjustments, duplicate transactions, returns, multiple currencies, mixed UoMs, missing receipt dates, invalid lots, period boundaries, rounding, historical cost changes (brief §18).
