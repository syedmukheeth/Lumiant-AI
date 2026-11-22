# BOM and Manufacturing Model

Code: `services/api/src/lumiant/planning/bom.py`. Data: canonical `bom_component` (see `MASTER_DATA_MODEL.md`). Tests: S21–S29, S39, C-F, `test_bom_duplicates_and_lifecycle`.

## Rules

- **Revision choice:** the released BOM valid on the production date (`valid_from ≤ date < valid_to`). A future revision never applies to an earlier date, so open orders keep their revision (S24, C-F).
- **Alternatives:** among valid BOMs the lowest `priority` wins (S29). Comparing alternatives on cost and lead time is planned.
- **Gross component quantity:** `parent qty × line qty ÷ base qty × (1 + scrap %) ÷ yield %` (S27: 100 × 2 × 1.05 ÷ 0.95 = 221.0526).
- **Phantoms:** a phantom item is exploded through and never planned or stocked (S28).
- **Multi-level:** subassemblies that are made are exploded recursively. Shared components are aggregated (S22, S23).
- **Blockers, not numbers:** circular structures (S22b), components missing from the item master (S25), make items without a BOM (S25) and BOM units without a conversion are reported as blockers. The affected requirement is not calculated.
- **Make or buy per plant:** `item_warehouse.procurement_type` (make, buy or SAP E/F/X). The same item can be made in Riyadh and bought in by Jeddah (`test_material_plan_uses_plant_procurement…`).
- **Lot sizing for production:** minimum run and multiple. The surplus output is visible as excess (S39).

## Not yet modelled

Routings and operations, work centres and capacity, co-products and by-products, rework, subcontracting, and engineering change orders beyond revision dates.
