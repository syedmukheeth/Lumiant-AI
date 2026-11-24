# Fine-Grained RBAC

All authorization is enforced in the API. The web hides what a role cannot use, but hiding is never the control.

| Level | Mechanism | Status | Evidence |
|---|---|---|---|
| Tenant | Principal's tenant from the session or token; one connector and mapping per tenant | Verified | isolation tests; `test_other_tenants_are_untouched` |
| Department | Expands to the department's warehouses | Verified (indirect) | `test_api.py` |
| Warehouse | Scope filter injected by the validator on every dataset with a scope key: stock, lots, movements, purchase lines, plant data, **customer orders** | Verified | `test_planner_sees_only_their_warehouse`, existing scope tests |
| Module | Permissions per route (`inventory:read`, `cost:read`, `chat:use`, `export:data`, `audit:read`, `admin:tenant` …); navigation sections computed server-side from permission **and** tenant data | Verified | `test_planning_sections_follow_role_and_tenant_data` |
| Dataset | Unmapped datasets are unavailable (409); planning modules are refused where the data does not exist | Verified | `test_other_tenants_are_untouched` |
| Field | `sensitivity=cost` fields need `cost:read`: valuation prices, stock values, **supplier quotations and freight** | Verified | `test_supplier_prices_need_cost_access`; existing cost-field tests |
| Operation | Read-only everywhere; exports need `export:data`; no write endpoints for business data | Verified | route review; `test_reports.py` |
| Assistant | Tools filtered by permission; the matcher refuses supplier and value questions without cost access; grounded answers only | Verified | `test_agent*.py`, `test_assistant_supplier_question_without_cost_access_is_refused` |

## Gaps (LA-13)

- Item master, supplier master, BOMs and alternates are tenant-wide master data for any reader (no department or warehouse scope).
- Only one sensitivity class (`cost`). A separate `procurement` class, so purchase prices are not tied to inventory valuation access, is planned.
- Extension attributes cannot be tagged sensitive.
- Physical table and column names are visible in provenance to all users. They should be shown only with a technical permission.
- Customer orders are warehouse-scoped but not customer-scoped (no sales-territory restriction).
