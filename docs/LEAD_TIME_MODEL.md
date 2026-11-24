# Lead Time Model

Lead times are kept separate and counted in **working days** on the tenant calendar (`planning/calendar.py`; default weekend Friday + Saturday, configurable holidays; S38).

| Lead time | Field | Used for |
|---|---|---|
| Supplier planned delivery time (per supplier–item) | `supplier_item.lead_days` | supplier eligibility by need date, earliest delivery, latest release (S48, S63) |
| Planning lead time per item and plant | `item_warehouse.lead_days` | MRP release dates for buy and make orders |
| Goods receipt processing | `item_warehouse.receiving_days` | added for buy orders |
| Quality inspection | `item_warehouse.inspection_days` | added for buy and make orders |
| Warehouse transfer | transfer lane `lead_days` | transfer arrival (C-D, C-O) |
| Manufacturing | `item_warehouse.lead_days` for make items | production start = need − lead; components needed on the start date |
| Operation, queue and setup times | — | planned (needs routings) |

## Rules

- **Unknown is unknown:** a missing lead time is `None`. Release and ready dates are then not calculated and the gap is a blocker (S80, demo-delta `RM-COPPER`), never 0.
- **Latest release:** need date − total lead time in working days. A release date before today is flagged as overdue (C-A).
- **Earliest ready:** today plus the lead time, chained through components for make orders. It is used for honest promise dates (S02b, C-A).
- **Quoted vs actual:** quoted lead times come from supplier–item data. Actual reliability is the on-time % from deliveries, shown separately (C-C, C-G). Historical averages are never treated as guaranteed dates; variability buffers are planned.
