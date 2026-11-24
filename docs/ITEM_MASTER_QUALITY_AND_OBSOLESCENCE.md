# Item Master Quality and Obsolescence

Code: `planning/duplicates.py`, `planning/obsolescence.py`. API: `GET /api/planning/duplicates`, `GET /api/planning/lifecycle`. Assistant: `duplicate_items`, `lifecycle_review`. Tests: S69, S74, C-E, C-F, C-K, `test_bom_duplicates_and_lifecycle`.

## Duplicate detection

**Normalisation:** upper case; punctuation removed; common abbreviations unified (STAINLESS STEEL / S/S → SS, INCH → IN, MILLIMETRE → MM); units joined to numbers (50 mm → 50MM).

| Verdict | When |
|---|---|
| `probable_duplicate` (high) | identical normalised description, or the same manufacturer part number, with no contradiction (S69 D1/D2, D4/D5) |
| `possible_duplicate` (medium) | descriptions at least 85% similar, same numbers and attributes (C-E bolts) |
| `conflict` (medium) | same product signals but different units, or the same part number with contradicting attributes. Needs correction after review (S69 D6/D7) |
| `different_specification` (low) | similar wording but different sizes, grades or other attributes. Not a duplicate, and never a substitute (S69 D1/D3, D8/D9) |

Comparisons run within blocks (same part number, or same item group and first word) to stay near-linear. Each finding lists its reasons. **Nothing is merged, renamed or deleted**; BOM references stay intact (C-E).

## Lifecycle review

| Verdict | Evidence required |
|---|---|
| `obsolete_candidate` | stock on hand, no issue movement for the threshold (default 365 days), no open demand, no use in a released BOM valid today or on an open order's date, not critical |
| `critical_keep` | marked critical (e.g. a spare for critical equipment). Kept however long it has not moved (C-K) |
| `superseded_run_down` | superseded item. Shows how much open demand still needs it and the possible excess (C-F: 60 needed, 40 excess) |
| `slow_moving_review` | no movement for the slow threshold (180 days) |
| `expiring_action` | expiring lot quantity vs demand (implemented, not yet covered by a check) |
| `active` | demand or active BOM use |

On tenants that do not map item criticality, the assistant still says it cannot predict obsolescence instead of judging from inactivity (existing golden test). Every verdict is for review by an authorised user; nothing is disposed of or blocked automatically.
