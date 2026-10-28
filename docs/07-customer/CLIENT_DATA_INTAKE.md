# Client Data Intake — SAP exports (M8)

_Structure only. This document never contains values from the client files (no codes, amounts, names or counts
taken from them). Where the shape of the data matters it is described qualitatively._

## 1. Status and authorization
- The client sent two SAP list exports as XLSX files. **Owner decision (2026-10-27, recorded in
  `../logs/sessions/2026-10-27-session-03.md`):** load the real files **only on the owner's machine**, under
  `services/api/var/private/` (git-ignored), never commit them or anything derived from them, never put real values
  in code, logs or docs; build a synthetic twin with the same layout (`demo-gamma`) for CI and demos.
- The tenant is classified `customer_extract` (ADR-0008): development only, dev sign-in only behind
  `LUMIANT_ALLOW_CUSTOMER_EXTRACTS=true`, the API refuses to start in production with it, the UI shows
  "CLIENT EXTRACT · CONFIDENTIAL · LOCAL", exports are stamped CONFIDENTIAL, external AI stays off.
- This is **not** a connection to a client system and not evidence of production readiness: it is a one-off snapshot.

## 2. The two files

| File | Looks like | Grain (one row =) | Key |
|---|---|---|---|
| *Warehouse Stocks of Material* | SAP **MB52** warehouse stock list | material × plant × storage location | Plant, Storage Location, Material |
| *Material Master* | SAP material master with valuation (MARA/MARC/MBEW fields) | material × plant (× valuation type, always blank) | Material, Plant |

Shape observed (qualitative): the stock list covers one plant and many storage locations, most rows are all-zero, a
small share of lines holds most of the value; the master covers many plants and a single currency; price control is
mostly moving average (V) with some standard price (S); price unit is 1 or 100; the ABC indicator is mostly blank;
the MRP type is mostly `ND` (no planning).

**SAP total rows.** The stock list ends with a block of total rows: Plant, Material and Material type are blank;
there is **one row per unit of measure** carrying the quantity totals of that unit, and the first of them also
carries the grand totals of the two value columns. A naive sum over every row therefore counts value twice. The
importer excludes these rows from the data and uses them as control totals.

## 3. Column dictionary → canonical model

### Stock list (`sap_mb52`, 15 columns)
| SAP column | Stored as | Canonical (via view `v_stock`) |
|---|---|---|
| Plant | `plant` (text) | `stock_balance.warehouse_id` (scope key) |
| Storage Location | `storage_location` | `stock_balance.location_id` |
| Material type | `material_type` | `item.inventory_stage` (value map) + `item.attr_material_type` (raw) |
| Material Group | `material_group` | `item.item_group` |
| Material | `material` (text, leading zeros kept) | `stock_balance.item_id`, `item.item_id`, `item.item_code` |
| Material Description | `material_description` | `item.description` (when the master has none) |
| Base Unit of Measure | `base_uom` | `stock_balance.uom`, `item.base_uom` |
| Unrestricted / Quality Inspection / Transit and Transfer / Restricted-Use Stock / Blocked / Returns | `DECIMAL(18,3)` | one `stock_balance` line per non-zero status: `stock_status` = unrestricted / quality_inspection / in_transit / restricted / blocked / returns, `quantity` |
| Value Unrestricted, Value in QualInsp. | `DECIMAL(18,2)` | `stock_balance.source_value` on the unrestricted / quality-inspection lines |

No currency column: the currency comes from the master record of the same material and plant.

### Material master (`sap_material_master`, 17 columns)
| SAP column | Stored as | Canonical (via `v_item_warehouse` / `v_item`) |
|---|---|---|
| Material, Plant | text | `item_warehouse.item_id`, `item_warehouse.warehouse_id` |
| Valuation Type | text | not mapped (blank; split valuation is refused, §4) |
| Material Description, Material type, Material Group, Base Unit of Measure | text | `item.*` (client-level attributes) |
| Last Change | `DATE` | not mapped |
| Purchasing Group, Valuation Class | text | `item_warehouse.attr_purchasing_group`, `attr_valuation_class` |
| ABC Indicator | text | `item_warehouse.abc_class` (per plant in SAP, so not `item.abc_class`) |
| MRP Type | text | `item_warehouse.planning_type` (value map) + `attr_mrp_type` (raw) |
| Price control | text | `item_warehouse.price_control` (value map V→moving_average, S→standard) |
| Price, Price unit | `DECIMAL(18,2)`, `INTEGER` | `unit_price = Price ÷ Price unit` (exact, `DECIMAL(20,8)`) → `valuation_price` on stock lines and `item_warehouse`; `price_rounding = 0.005 ÷ Price unit` → `stock_balance.price_rounding` |
| Currency | text | `currency` on stock lines and `item_warehouse` |
| Created By | **not stored** | — (a person's user id; not needed) |

`stock_value` = quantity × valuation price (computed by the engine, per currency, never summed across currencies).

### Value maps (draft, SAP standard meanings)
`lumiant.ingest.sap_exports`: material types (ROH→RAW, HALB→SEMI, FERT→FINISHED, HAWA→TRADING, ERSA→SPARE,
VERP→PACKAGING, HIBE→CONSUMABLE, NLAG→NON_STOCK, UNBW→NON_VALUATED, DIEN→SERVICE, FHMI→TOOLING), MRP types (ND→none,
VB/VM/V1/V2→reorder_point, VV→forecast, PD/M0–M4→mrp), price control. Client-specific codes (e.g. Z-types) read
`unmapped` and are reported until the client explains them (Q-019, Q-021).

## 4. Import rules and checks (`lumiant-ingest sap`)
1. **Header contract:** exact SAP column names; missing, unexpected or duplicate columns stop the import and are named.
2. **Codes stay text** (leading zeros survive); a code that Excel turned into a number is refused.
3. **Numbers are exact:** `Decimal(str(cell))`; more decimals than the SAP field allows (3 for quantities, 2 for
   amounts) is refused, never rounded. Blank quantities on detail rows are refused.
4. **Total rows:** blank Plant + Material + Material type. They must form one block after the last detail row, have a
   unit of measure, one per unit.
5. **Control-total gate (hard):** per unit of measure, every quantity column of the detail rows must add up exactly to
   its total row; both value columns must add up exactly to the grand total. Otherwise **nothing is written**.
6. **Master:** Material and Plant required; a duplicate material/plant key (split valuation) stops the import.
   Unit price only where Price, Price unit (> 0) and Currency are present and the division is exact; otherwise the
   line stays unpriced and the manifest counts why (`valuation_issues`).
7. **Reported, not fixed:** duplicate plant/location/material keys, stock without master data, zero prices with stock,
   unit-of-measure differences to the master, source value vs quantity × price, master records without stock,
   inconsistent client-level attributes across plants.
   **Reconciliation rule:** SAP stores the stock value and shows the moving-average price rounded to 2 decimals per
   price unit, so a line only differs when |source value − quantity × price| > 0.01 + |quantity| × 0.005 ÷ price unit
   (`price_rounding` column, canonical `stock_balance.price_rounding`). With a plain 0.01 tolerance, pure price
   rounding showed up as false mismatches on the real files; with the rounding bound every compared line reconciled.
8. Error messages name rows and columns but never echo cell contents; the CLI prints counts and check results only.

## 5. What is written (all under `services/api/var/private/`, git-ignored)
- `client-sap/warehouse.duckdb` (atomic replace): raw `sap_mb52`, `sap_mb52_totals`, `sap_material_master`; views
  `v_stock`, `v_item`, `v_item_warehouse`, `v_warehouse`; `_extract_metadata` (as-of → "data as of" in the UI);
  `_dataset_info` (`synthetic=false`, importer version, manifest).
- `client-sap/manifest.json`: input sha256 and row counts, total rows excluded, control totals and gate result,
  valuation issues, stock/master/reconciliation counts.
- `tenants/client-sap.yaml`: generated tenant config (`customer_extract`, plants as warehouses under one placeholder
  department, roles, dev users `client-sap.admin` and `client-sap.viewer`, value maps, source hints).

## 6. Data-quality checks in the app (Risks → Master-data quality)
Stock lines without master data for their plant · zero valuation price · without valuation price · source value ≠
quantity × price · duplicate stock keys · codes without a value map (per value-mapped field) · item–plant records
without ABC class (share) · records with no stock planning (share, info) · master records without stock (share, info).

## 7. What it unlocks
Inventory value per currency (status, plant, storage location, stage, group), stock-status split (unrestricted,
quality inspection, blocked, …), explorer with search and status filter, value-by-warehouse and stock-listing
reports, source-vs-computed value reconciliation per line, master-data gap analysis, concentration of value.

## 8. What is missing → next files to request (also `OPEN_QUESTIONS.md`)
| Capability | Missing | File to request |
|---|---|---|
| Dormant / slow-moving, consumption, turnover, FIFO, moving-average recomputation | movements | **MB51 / MSEG**, 24 months (posting date, movement type, quantity, amount, plant, storage location, batch) |
| Below-reorder, excess, safety stock | reorder point, safety stock, max level | **MARC** (MINBE, EISBE, MABST, DISMM, plant) |
| Expiry, FEFO, batch value | batches, shelf life | **MCHB / MCH1** (batch stock, expiry / production dates) |
| Readable names | plant and storage location names | **T001W / T001L** |
| Latest purchase price, open supply | purchase order lines | **EKKO / EKPO** (ME2M) |
| Supplier views | vendor master | **LFA1** |

## 9. How to run (owner's machine only)
```
cd services/api
uv run lumiant-ingest sap --stock "<path>/Warehouse Stocks of Material.XLSX" --master "<path>/Material Master.XLSX" --tenant client-sap --as-of YYYY-MM-DD
# then start the API in development with:
LUMIANT_PRIVATE_TENANTS_DIR=var/private/tenants LUMIANT_ALLOW_CUSTOMER_EXTRACTS=true
```
Stop the API before re-importing (DuckDB file lock). `git status` must show nothing under `services/api/var/`.

## 10. Synthetic twin (`demo-gamma`)
`uv run lumiant-synthetic generate --tenant demo-gamma` writes two XLSX files in exactly this layout (generated
values, SAR, invented plants GM01–GM03, ~29 storage locations, mostly all-zero rows, SAP total rows, V/S price
control, price unit 1/100) with planted cases for every check in §6, then runs the same importer into
`data/synthetic/demo-gamma.duckdb`. Tests compare every total and check count with values computed directly from the
XLSX files (`tests/integration/test_sap_extract.py`).
