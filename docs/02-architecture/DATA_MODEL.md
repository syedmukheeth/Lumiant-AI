# Canonical Data Model

Status: **Designed** (M1 implements it in `services/api/src/lumiant/canonical/catalog.py`; that file is authoritative if this doc drifts).

## Approach

A **semantic layer**, not a physical database we own. Canonical datasets describe *meaning*; each tenant's mapping points them at the customer's physical tables/views. We do not copy customer data into our own tables.

- Core fields are typed and named consistently across customers.
- Customer-specific columns are mapped as **extension attributes** (`attributes.<name>` with a declared type), so ~100+ item fields are supported without schema changes.
- Each field carries metadata used by the validator and the agent:

| Metadata | Values | Used for |
|---|---|---|
| `type` | string, integer, decimal, date, datetime, boolean | coercion, operator validity |
| `role` | key, dimension, measure, date, attribute | grouping/aggregation validity |
| `sensitivity` | none, cost | permission `cost:read` |
| `scope_key` | true on `warehouse_id` | scope injection |
| `unit_field` / `currency_field` | name of companion field | UoM/currency safety rails |
| `description` | text | agent context, UI tooltips |

## Datasets

### `item` — item master
| Field | Type | Role | Notes |
|---|---|---|---|
| item_id | string | key | stable id |
| item_code | string | dimension | customer code (parsing rules M2) |
| description | string | attribute | untrusted text (may contain injection attempts) |
| item_group | string | dimension | e.g. RUBBER, FLAMMABLE |
| inventory_stage | string | dimension | RAW, SEMI, FINISHED, SPARE, … |
| abc_class | string | dimension | **as assigned in source** |
| base_uom | string | dimension | |
| status | string | dimension | ACTIVE, BLOCKED, OBSOLETE… |
| lot_tracked | boolean | dimension | |
| shelf_life_days | integer | attribute | |
| storage_temp_min / storage_temp_max | decimal | attribute | °C |
| flammability_class | string | attribute | |
| default_supplier_id | string | key | |

### `warehouse`
warehouse_id (key, scope_key) · name · department_id · site · temperature_controlled (bool) · flammable_storage (bool)

### `storage_location`
location_id (key) · warehouse_id (scope_key) · name

### `stock_balance` — on-hand snapshot
| Field | Type | Role | Notes |
|---|---|---|---|
| item_id | string | key | join → item |
| warehouse_id | string | key, scope_key | join → warehouse |
| location_id | string | dimension | |
| lot_id | string | dimension | nullable |
| quantity | decimal | measure | unit_field = uom |
| uom | string | dimension | |
| valuation_price | decimal | attribute | **sensitivity=cost**, currency_field = currency |
| currency | string | dimension | |
| stock_value | decimal | measure (computed) | = quantity × valuation_price; **sensitivity=cost**; currency_field = currency |

### `reorder_policy` — customer-defined
item_id · warehouse_id (scope_key) · min_stock · max_stock · reorder_level (decimal, uom = item base_uom). Missing row = "no policy" (never invented).

### `lot`
lot_id · item_id · warehouse_id (scope_key) · receipt_date · expiry_date · supplier_id · unit_cost (cost) · currency

### `inventory_transaction`
txn_id · txn_type (RECEIPT, ISSUE, TRANSFER_IN, TRANSFER_OUT, ADJUSTMENT, RETURN) · item_id · warehouse_id (scope_key) · location_id · lot_id · quantity (signed) · uom · unit_cost (cost) · currency · posting_date

### `purchase_record`
po_id · line · item_id · supplier_id · warehouse_id (scope_key) · order_date · receipt_date · quantity · uom · unit_price (cost) · currency · status

### `supplier`, `department`
supplier_id · name · country — department_id · name

## Approved joins (only these compile)

| From | To | On |
|---|---|---|
| stock_balance | item | item_id |
| stock_balance | warehouse | warehouse_id |
| stock_balance | reorder_policy | item_id + warehouse_id |
| reorder_policy | item | item_id |
| reorder_policy | warehouse | warehouse_id |
| lot | item | item_id |
| inventory_transaction | item | item_id |
| purchase_record | item | item_id |
| purchase_record | supplier | supplier_id |

Joined fields are addressed as `item.item_group`, `warehouse.name`, etc. in QueryPlans.

## Safety rails encoded in the model

1. Measures with a `currency_field` are always grouped by that currency (no cross-currency sums without an approved FX table — none exists yet).
2. Measures with a `unit_field` are always grouped by that UoM (no cross-unit sums without an approved conversion table — none exists yet).
3. `sensitivity=cost` fields require `cost:read` — whether selected, filtered, sorted or aggregated.
4. `scope_key` fields receive injected scope filters.

## Brief entities not modelled as datasets (yet) and why

| Entity | Where it lives |
|---|---|
| ItemAttribute | extension attributes on `item` |
| ItemClassification / ItemGroup | dimensions on `item`; computed ABC in M2 |
| UnitOfMeasure / conversions | M2 table when a customer supplies conversions |
| CostRecord | `lot.unit_cost`, `purchase_record.unit_price`, `stock_balance.valuation_price`; M2 cost layers computed |
| StorageRequirement | item attributes; location capabilities in `warehouse` (M2 extends) |
| InventoryRisk | output of analyses, not stored source data |
| DataSource / DataMapping | tenant YAML |
| User / Role / Department | tenant YAML (dev) → IdP + app DB (M6) |
| AuditEvent | app DB table `audit_event` |
