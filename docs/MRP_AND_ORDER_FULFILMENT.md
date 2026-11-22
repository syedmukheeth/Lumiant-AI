# MRP and Order Fulfilment

Code: `services/api/src/lumiant/planning/mrp.py` (`run_mrp`, `MrpResult.fulfilment`, `excess_supply`). API: `GET /api/planning/fulfilment`, `GET /api/planning/material-plan`. Assistant: `order_fulfilment`, `material_plan`. Tests: S01–S16, S23, S26–S52, C-A, C-B, C-I, C-M, C-N, integration tests on demo-delta.

## Availability

- **Usable today:** status unrestricted, company-owned and not expired.
- **Not usable:** quality inspection, blocked, returns, restricted, in transit, expired, customer-owned and consignment stock. These are shown per status (S10, S11b).
- **Reservations** are taken off usable stock first (S11).
- **Safety stock** is protected from customer demand (`AllocationPolicy.protect_safety_stock`). A shortfall becomes its own requirement, planned last (S16, S16b).
- **Open purchase, production and transfer orders** are supply on their due date only (S14).

## Netting (per item and warehouse, lowest BOM level first)

1. Demand is sorted by the tenant's allocation keys (default due date → priority → order date), so scarce stock goes where the policy says (S03, S03b).
2. Each demand consumes supply available by its need date first, then later supply. A late receipt still covers the demand, so nothing is bought twice, but the line is reported late with the PO and its date (S07, S08, S62).
3. Approved alternates cover what is left, using only stock the alternate does not need for its own demand (two passes, S26c).
4. The remainder becomes a planned order:
   - it is lot-sized (lot-for-lot, fixed, minimum, multiple);
   - it is merged with other demand for the same item, warehouse and date, so MOQ applies once (S23, S52);
   - it is due on the need date and released `lead time` working days earlier;
   - a missing lead time is a blocker (S80).
5. Make orders explode through the BOM valid on the release date into dependent demand on that date.

## Promise dates

Each planned order's earliest ready date is today, or the readiness of its components, plus its lead time. It is never earlier than the need date. A customer line is on time when every quantity covering it is ready by its due date. Otherwise the line shows its ready date, working days late, and the chain of reasons:
- a late PO;
- a component's earliest date;
- a missing lead time or BOM.

Combined A: 400 from stock, 600 to make, impeller-equivalent short, ready 8 working days late. With the alternative supplier's lead time it is on time (C-A2).

## Pegging and excess

Every coverage records its source (stock, receipt, alternate, planned) and the order lines it serves. Open receipts and lot-size surplus that no demand uses are reported as possible excess (S06, C-N).

## Not built

Forecast demand, statistical safety stock, FEFO lot choice, capacity, and order-change history (demand is the current order state, which avoids double counting by design).
