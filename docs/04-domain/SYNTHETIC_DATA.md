# Synthetic Data

> **All data in this project is synthetic until a customer approves real data.** It is generated, deterministic, and labelled as synthetic both in the database (`_dataset_info.synthetic = true`) and in the tenant config (`data_classification: synthetic`). The API reports `synthetic: true` if **either** source says so, and the UI shows a permanent **SYNTHETIC DEMO DATA** badge.

## Generate

```bash
cd services/api
uv run lumiant-synthetic generate --all          # all three tenants, default seeds
uv run lumiant-synthetic generate --tenant demo-alpha --seed 42
```
Output: `services/api/data/synthetic/demo-alpha.duckdb`, `demo-beta.duckdb` and `demo-gamma.duckdb` (gitignored; regenerate any time, but stop the API first because of the DuckDB file lock). The same seed and as-of date always produce the same records (covered by a test).

## Tenants

| | demo-alpha | demo-beta |
|---|---|---|
| Physical style | SAP-*style* (illustrative): `ZV_MATERIAL`, `ZV_STOCK`, `ZV_BATCH`, `ZV_MOVEMENT`, `ZV_REORDER`, `ZV_PLANT`, `ZV_SLOC`, `ZV_VENDOR`, `ZV_PURCHASE`, `ZV_DEPT` with `MATNR`, `WERKS`… | snake_case in schema `inv`: `item_master`, `stock_on_hand`, `lots`, `stock_movements`, `reorder_rules`, `warehouses`, `bins`, `suppliers`, `purchase_lines`, `business_units` |
| Currency | USD | EUR **and** GBP (per warehouse) |
| Departments / warehouses | 3 / 6 | 2 / 3 |
| Items (default run) | 600 → 81,935 movements, 1,160 stock lines | 250 → 32,686 movements, 454 stock lines |
| History | 24 months of transactions | 24 months |
| Item codes | 10-digit numeric (digits 1–2 category, 3–4 material, last 6 serial) | `GG-NNNN-X` alphanumeric |
| Extract time (as-of) | generation time (UTC) in `_extract_metadata` | generation time in `inv._extract_metadata` |

### demo-gamma — twin of the client SAP exports (M8)
Not generated as tables: `synthetic/sap_twin.py` writes the two client XLSX files in the **exact client layout**
(MB52-style stock list with SAP total rows; material master valuation list) with generated values only — SAR, invented
plants GM01 (stock) and GM02/GM03 (master only), 29 storage locations, SAP standard material types plus one
deliberately unmapped type `ZDMO`, ~86 % all-zero rows, V/S price control, price unit 1/100, 9-digit material numbers
with leading zeros — and then runs the **same importer** as the client files (`lumiant.ingest.sap_exports`). Default
1,500 materials (≈5k stock rows, ≈1.9k master rows, ~8 s). Planted cases (returned as `scenarios`): stock without
master, zero price with stock, moving-average drift (source value ≠ quantity × price), one duplicate
plant/location/material key, unmapped material type, an inexact price unit (10.00 per 3), master-only records and
other-plant records. The tenant YAML `config/tenants/demo-gamma.yaml` is produced by the same mapping generator as
the client tenant (a test keeps them in sync). Dev users `gamma.admin` (all plants) and `gamma.viewer` (GM01, no cost).

## How it is generated

1. Master data: departments, warehouses, suppliers, items (group, stage, assigned ABC, UoM, storage attributes, lot tracking).
2. Item–warehouse assignment, then a per-pair event stream across 24 months:
   - **receipts** create lots (receipt date; expiry for shelf-life items; unit cost drifting with noise and occasional spikes),
   - **issues** consume the oldest lots first (never below zero),
   - **transfers**, **± adjustments**, **returns**.
3. **Balances = the sum of transactions** per item/warehouse/location/lot at extract time (tested).
4. Valuation price = the generator's own moving weighted average per item–warehouse (stands in for an "ERP value"; the M2 costing engine will reconcile against it with independent code).
5. Reorder policies (min/max/reorder level) for most pairs; some are deliberately missing.

## Planted scenarios (for tests and demos)

| Scenario | Purpose |
|---|---|
| Item–warehouse below reorder level | below-reorder analysis |
| Policy present but **zero** stock lines | zero-stock edge case |
| Stock above max | excess (M2) |
| No issues for 9+ months | dormant/slow-moving (M2) |
| Expired and near-expiry lots | expiry (M2) |
| Missing reorder policy | `no_policy` count |
| Missing valuation price | `missing_valuation_price` warning |
| Invalid item codes | master-data quality (M2) |
| Description containing a prompt-injection string | AI security tests (M3) |

The exact planted ids are written to `_dataset_info` (key `scenarios`) so tests can look them up and never hard-code them.
