# Classifications

Every classification is an **independent dimension** on `item` (storage capability lives on `warehouse`). Customer values are mapped, never invented.

## Inventory stage
Canonical values: `RAW`, `SEMI`, `FINISHED`, `SPARE` (customer-defined extras allowed).
In M1 the synthetic writer stores canonical values directly in both tenants. Value-level mapping (for example `ROH → RAW`) is planned and tracked in `logs/ISSUES.md`.

## ABC
- **M1:** `abc_class` *as assigned in the source item master*, labelled "ABC (assigned)" in the UI.
- **M2:** computed ABC with a configurable method, period and thresholds, shown next to the assigned class with differences highlighted. No universal thresholds.

## Item groups (synthetic demo)
`RUBBER`, `FLAMMABLE`, `TEMP_SENSITIVE`, `MECH_SPARES`, `ELECTRICAL`, `PACKAGING`, `FASTENERS`.

## Storage requirements
- Item side: `storage_temp_min`, `storage_temp_max`, `flammability_class`, plus extension attributes such as humidity and handling notes.
- Warehouse side: `temperature_controlled`, `flammable_storage`.
- A mismatch can be flagged (M2) only when **both** sides are mapped and populated; otherwise the check is turned off and says why. Never infer requirements from item names.
