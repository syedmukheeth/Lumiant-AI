# Master Enterprise Data Model

The canonical model is defined in code (`services/api/src/lumiant/canonical/catalog.py`). This page indexes it; field-level detail for the planning extension is in `MASTER_DATA_MODEL.md` and the original inventory model in `02-architecture/DATA_MODEL.md`.

| Domain | Canonical datasets | Status |
|---|---|---|
| Items | `item` (incl. manufacturer, MPN, lifecycle, supersession, criticality), `item_warehouse` (per-plant planning: make/buy, lead times, safety stock, lot rules) | Implemented |
| Locations | `warehouse`, `storage_location`, `department` | Implemented |
| Stock | `stock_balance` (status, lot, valuation), `lot` (expiry) | Implemented |
| Movements | `inventory_transaction` | Implemented |
| Policies | `reorder_policy` | Implemented |
| Suppliers | `supplier` (approval, status, certification and expiry, currency, terms), `supplier_item` (price*, MOQ, multiple, lead time, validity, approval, freight*, duty, capacity) | Implemented |
| Purchasing | `purchase_record` (open quantity, expected date, received and rejected quantities) | Implemented |
| Engineering | `bom_component` (header attributes plus lines), `item_alternate` | Implemented |
| Demand | `customer_order_line` | Implemented |
| FX, transfer lanes, work centres, routings, calendars per plant, forecasts, production orders, serial numbers | — | Planned (engine-side models exist for FX, lanes and calendar) |
| Scenario executions, recommendations, approvals | audit records (`planning:*`, `planning:capability_gap`) | Partial: persisted as audit events; no approval workflow store yet |

\* cost-sensitive: needs `cost:read`.

## Cross-cutting rules

- **Tenant-specific attributes:** extension `attributes` in tenant YAML (existing mechanism).
- **Source identifiers:** canonical keys keep the source codes (item, supplier, PO, order ids). Physical table and column names appear in provenance.
- **Effective dates:** BOM revisions, alternates, quotations, FX rates.
- **Units and currency:** `unit_field` / `currency_field` rails in the validator. The planning engine converts units only with a known conversion and never adds currencies together.
- **Provenance, freshness and authority:** a provenance block on every query result; a tenant freshness object drives `stale` warnings. Source-authority rules for multiple sources are planned (scenario 84).
