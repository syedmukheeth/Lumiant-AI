# Supplier Master and Evaluation

Code: `services/api/src/lumiant/planning/suppliers.py` (`compare_suppliers`). Data: canonical `supplier`, `supplier_item`, received `purchase_record` lines (delivery and price history). API: `GET /api/planning/suppliers` (needs `cost:read`). Assistant: `supplier_comparison`. Tests: C-C, C-G, C-H, C-L, S48–S63, `test_supplier_comparison_respects_eligibility_and_policy`.

## Eligibility (an ineligible offer is listed with its reasons, never recommended)

- Supplier exists, is approved and active.
- Mandatory certificates are valid on the need date. An expired certificate is accepted only if the tenant's policy sets an explicit exception (S56).
- The supplier–item relationship is approved and the quotation is valid today.
- An approved exchange rate exists for the quote currency (S58).
- The supplier can deliver by the need date: `today + lead + receiving + inspection` working days (S48). A missing lead time means the date cannot be checked.
- Optional quality and delivery gates: maximum rejection %, minimum on-time % (C-C quality-critical, C-G).

## Comparable cost

- **Unit price:** the price break that applies to the order quantity, ÷ price unit, × the latest exchange rate effective today. The rate and its date are shown.
- **Order quantity:** the need rounded up to MOQ and multiple. The excess is shown (S51, C-H).
- **Landed unit cost:** price + freight + duty % + other charges, where known. Unknown freight or duty is listed and never treated as 0 (S59, C-L).
- **Cost per unit needed:** total cost ÷ quantity needed. Buying 500 to use 120 counts against the offer, so MOQ excess is never hidden by a low unit price (C-H).

## Evidence

Rejection % and on-time % come from received deliveries of that item. With fewer than `min_evidence_lots` deliveries, the result is **insufficient evidence**: no score is invented, and the offer ranks after scored offers (S57). The price is compared with the last purchase price and with the average over history, each with its date (S50).

## Ranking policies (no universal winner)

| Policy | Mode | Rule |
|---|---|---|
| `balanced` | weighted | 0.4 price, 0.3 quality, 0.2 on-time, 0.1 lead time, each normalised to the best eligible offer |
| `urgent` | fastest | earliest delivery among eligible offers |
| `lowest_cost` | cheapest | lowest known cost per unit needed |
| `quality_critical` | quality | lowest rejection rate, with a 3% rejection limit |

The same three suppliers rank B, A, C (balanced), A first (lowest cost), C only (urgent, 5-day need) and B first (quality-critical) in combined C. If no single supplier has the capacity, a split across eligible suppliers in rank order is suggested (S55). Every result says "recommendation for review; no purchase order is created or approved".

## Confidentiality

Prices are cost-sensitive: no `cost:read`, no comparison (API, tool and matcher all refuse; tested). Lumiant has no supplier-facing access, so one supplier's quotation can never be shown to another.
