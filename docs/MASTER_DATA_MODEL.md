# Master Data Model (planning extension)

The canonical model (`services/api/src/lumiant/canonical/catalog.py`) is extended rather than duplicated. Tenants map their ERP tables onto it in YAML (ADR-0006). All new fields are optional, so existing tenants are unaffected: every existing test still passes. Field metadata drives the query engine as before: `sensitivity=cost` requires `cost:read`, `scope_key` injects warehouse scope, and `unit_field` / `currency_field` enforce the UoM and currency rails.

## New datasets

| Dataset | Grain | Key fields | Scope / sensitivity | SAP | Odoo 18 | Oracle Fusion |
|---|---|---|---|---|---|---|
| `bom_component` | BOM line, with header attributes repeated | bom_id, parent_item_id, revision, alternative, priority, base_quantity, yield_pct, status, valid_from/to, component_item_id, quantity, uom, scrap_pct, sequence | master data (not scoped) | STKO/STPO (+ MAST), CS03 | `mrp.bom`, `mrp.bom.line` (type normal/phantom) | Item structures / work definitions |
| `item_alternate` | primary → alternate | item_id, alternate_item_id, ratio, priority, approved, valid_from/to, max_share_pct, customer_id, note | master data | Alternative item groups in BOM (ALPGR), material substitution | `mrp.bom.line` alternatives / product variants (custom) | Substitute components, item relationships |
| `supplier_item` | supplier × item | supplier_id, item_id, supplier_item_code, price*, currency, price_unit, uom, moq, order_multiple, lead_days, valid_from/to, approved, freight_per_unit*, duty_pct, capacity | `price` and `freight` need `cost:read` | Purchasing info record (EINA/EINE), source list (EORD) | `product.supplierinfo` (price, min_qty, delay) | Approved supplier list, BPA lines |
| `customer_order_line` | order line | order_id, line, customer_id, item_id, warehouse_id, quantity, uom, due_date, priority, order_date, status | warehouse-scoped | VBAP/VBEP (open quantity, requested date) | `sale.order.line` | Order management fulfilment lines |

## Extended datasets

| Dataset | New fields | Purpose |
|---|---|---|
| `item` | manufacturer, mpn, lifecycle_status, superseded_by, critical | duplicates, supersession, critical spares |
| `item_warehouse` | procurement_type (make / buy, also SAP E / F / X), phantom, lead_days, receiving_days, inspection_days, safety_stock, lot_rule, lot_size, min_lot, lot_multiple | per-plant planning parameters (SAP MARC: BESKZ, DZEIT/PLIFZ, WEBAZ, EISBE, DISLS, BSTMI, BSTRF) |
| `purchase_record` | expected_date, open_quantity, received_quantity, rejected_quantity | open supply by date; delivery reliability and quality history |
| `supplier` | approved, status, certification, certification_expiry, currency, payment_terms | eligibility and compliance |

## Planning model (engine side)

`planning/model.py` holds plain, immutable records built by `planning/loader.py` (from canonical rows) or `planning/builder.py` (from YAML or dicts):
- `Item`, `Bom` / `BomLine`, `AlternateRule`, `StockLine` (status, lot, expiry, owner), `Reservation`, `Supply`, `DemandLine`, `PlanningPolicy`, `Calendar`, `AllocationPolicy`, `UomConversion`;
- `Supplier`, `Certification`, `SupplierOffer` (with `PriceBreak`), `DeliveryRecord`, `PriceRecord`, `FxRate`, `SupplierPolicy`.

Unknown values stay `None` (lead time, freight, duty, capacity) and are reported. They are never replaced by 0.

## Provenance and governance

- **Source and audit:** every canonical read goes through a validated query plan whose provenance (tenant, dataset, filters, scope, row count, timestamp) is recorded in the audit log, plus one `planning:*` audit record per run. Synthetic data carries `_dataset_info.synthetic = true`.
- **Freshness:** the tenant's freshness object drives a `stale_data` warning on every planning result.
- **Status of a value:** imported (mapped from the source), configured (policies, presets in `planning/service.py`) or calculated (engine output with its `explanation`).
- **Not yet modelled:** per-field source timestamps and data-quality flags per record, exchange rates, work centres and routings, customer master, forecast demand, transfer lanes as a canonical dataset (they are an engine input today; scenario fixtures provide them).
