# Procurement Decision Engine

Procurement decisions combine the MRP (what, how much and when) with supplier evaluation (from whom and why). Both are read-only recommendations.

| Question | Answer from | Evidence |
|---|---|---|
| What must we buy, net of stock and open POs? | `material_plan` → planned buy orders (net, lot-sized quantity, reason) | S02, S11, C-M |
| Do we already have it on order? | open PO lines are supply on their date; late POs are flagged, not re-bought | S06, S08, S14 |
| When must the PO be released? | `need date − (lead + receiving + inspection)` working days; overdue releases are flagged | S38, S63, C-A |
| From whom? | `supplier_comparison` under the tenant's policy | C-C |
| Is the quote reasonable? | % vs last and average purchase price | S50, C-G |
| Is the MOQ worth it? | order quantity, excess and cost per unit needed | C-H, S52 |
| One supplier cannot supply everything? | split across eligible suppliers in rank order | S55 |
| Emergency? | `urgent` policy with the production start date as need date; what-if with that lead time | C-A, C-A2 |
| No approved source? | sourcing gap; "do not raise a purchase order until procurement reviews" | S60 |

**Not automated, by design:** creating, approving or sending purchase orders; contacting suppliers; changing master data. **Not built yet:** supplier risk scoring beyond quality and delivery, contract and BPA price validity, purchase return documents, FX rates and charges from canonical data.
