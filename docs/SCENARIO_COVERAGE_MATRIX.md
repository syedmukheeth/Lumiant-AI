# Scenario Coverage Matrix

_22 Nov 2026. Per-scenario detail is in `SCENARIO_CATALOGUE.md`. A scenario counts as Tested only when an automated check passes. A screen, or code without a check, does not count._

| Area | Scenarios | Tested | Implemented | Partial | Planned | Blocked |
|---|---|---:|---:|---:|---:|---:|
| Customer and orders | 1–10 | 8 | 0 | 2 | 0 | 0 |
| Availability and balancing | 11–20 | 6 | 0 | 3 | 1 | 0 |
| BOM and manufacturing | 21–33 | 8 | 0 | 2 | 3 | 0 |
| Production and lead times | 34–41 | 4 | 0 | 1 | 1 | 2 |
| Alternate items | 42–45 | 4 | 0 | 0 | 0 | 0 |
| Suppliers and procurement | 46–68 | 21 | 0 | 2 | 0 | 0 |
| Item master and lifecycle | 69–79 | 7 | 1 | 1 | 2 | 0 |
| Data quality and exceptions | 80–89 | 6 | 1 | 1 | 2 | 0 |
| **Total (89)** | | **64** | **2** | **12** | **9** | **2** |
| Combined A–O (15) | | **14** | 0 | **1** (J) | 0 | 0 |

Notes:
- Scenario 4 counts as Partial even though combined A is tested, because expedite costs and production re-sequencing are not modelled.
- Scenarios 86 and 87 are covered by existing admin features (drift check, unmapped columns), not by the new planning engine.
- The 9 Planned and 2 Blocked scenarios share a few missing data families: work centres, routings and calendars (35–37), forecasting history (18), co-product and rework structures (30–32), supplier code matching (71), lifecycle sources (78), multi-source reconciliation (84) and transaction deduplication (89).

## Test counts behind the matrix

| Suite | Checks | Result (22 Nov 2026, Windows) |
|---|---:|---|
| Scenario harness `tests/unit/test_planning_scenarios.py` (4 YAML files) | 85 | 85 passed |
| Integration `tests/integration/test_planning.py` (demo-delta: API, tools, scope, cost, grounding) | 17 | 17 passed |
| Full API suite | 753 + 6 skipped | 753 passed, 6 skipped (need Redis or Postgres) |
| Lint and types | ruff, ruff format, mypy strict | clean |

## Permission and isolation checks

| Rule | Evidence |
|---|---|
| Supplier prices need `cost:read` (service, API, assistant) | `test_supplier_prices_need_cost_access`, `test_planning_api_scope_and_permissions`, `test_assistant_supplier_question_without_cost_access_is_refused` |
| Warehouse scope on orders | `test_planner_sees_only_their_warehouse`, API test |
| Other tenants unaffected | `test_other_tenants_are_untouched`; the existing 651 tests still pass |
| Assistant answers grounded | `test_assistant_routes_planning_questions` (grounding passed for all 8) |
