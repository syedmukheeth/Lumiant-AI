# Enterprise Product Audit

_23 Nov 2026, branch `work/resume-phase-b` (last pushed commit `d3abd43`; this session's changes uncommitted). Source of truth: the code and the tests, not page existence._

**Labels**
- **Verified**: implemented and proven by an automated test or a recorded browser check.
- **Implemented**: built but not fully verified.
- **Partial**: partially built.
- **Planned**
- **Missing**: not started.
- **Blocked**: waits on an external dependency.

## 1. Feature coverage matrix

| Area | Capability | Status | Evidence |
|---|---|---|---|
| Inventory | Overview dashboard, KPIs, insight feed | Verified | web unit and e2e suites; `test_metrics*`, `test_insights*` |
| Inventory | Inventory explorer (balances, filters, sort, paging) | Verified | e2e; `test_api.py` |
| Inventory | Risks: excess, dormant, expiring, data quality | Verified | `test_m2_analyses.py`; e2e |
| Inventory | Costs: costing methods, ABC | Verified | `test_costing.py` |
| Inventory | Reports and exports (audited, formula-safe) | Verified | `test_reports.py` |
| Inventory | Serial numbers, consignment, WIP as stock categories | Partial | stock owner and status in the planning model; no serial-number dataset |
| Governance | Admin: schema drift, capability matrix, reconciliation, audit explorer | Verified | `test_admin.py` |
| Governance | Source provenance on every result | Verified | provenance tests; UI provenance button |
| Planning | BOM explosion (revisions, multi-level, phantom, scrap/yield, cycles) | Verified | scenario harness S21–S29 |
| Planning | Time-phased MRP, pegging, promise dates, lot sizing, safety stock | Verified | S01–S16, S23, S38–S52, C-A/B/I/M/N |
| Planning | Order fulfilment workspace (web) | Verified | `/planning` on demo-delta; e2e `planning.spec.ts` |
| Planning | Material plan and BOM explorer (web) | Verified (browser) | `/planning` tabs |
| Planning | Production capacity, routings, work centres, downtime | Blocked | no source data; `assess()` reports the gap |
| Planning | Forecast demand, seasonality | Planned | |
| Procurement | Supplier comparison engine (eligibility, FX, landed cost, evidence, policies, split) | Verified | C-C/G/H/L, S48–S63 |
| Procurement | Supplier comparison workspace (web) | Verified (browser) | `/suppliers` on demo-delta |
| Procurement | Customer commitment protection: delivery-first sourcing, exposure, split, fallbacks (engine, API, assistant, web) | Verified | C-P/P2/P3/Q/R; commitment integration tests; e2e `/commitments` |
| Procurement | Supplier master and performance pages (browse and maintain suppliers) | Missing | the comparison covers the pre-PO decision; a supplier directory page is not built |
| Procurement | FX rates and landed-cost charges from source data | Planned | engine supports them; canonical datasets not added |
| Master data | Duplicate detection (engine and web) | Verified | S69, C-E; `/master-data` |
| Master data | Lifecycle and obsolescence (engine and web) | Verified | S74, C-F, C-K; refuses without criticality data |
| Assistant | Rule-based assistant, grounding, permissions, Arabic and ERP terms, greetings | Verified | `test_agent*.py`, terminology evals |
| Assistant | Planning tools (8, incl. `customer_commitment`) | Verified | `test_planning.py` routing and grounding tests |
| Assistant | External LLM (Anthropic, Gemini) | Implemented | fake-client tests; no key, no tenant approval (blocked) |
| Integration | DuckDB connector, SAP list-export importer | Verified | `test_sap_extract.py` |
| Integration | SAP / Oracle Fusion / Odoo / SQL Server live connectors | Blocked | no authorised sandbox; `nomap` prototype only |
| Brand | Official Lumiant logos, theme-aware, brand palette | Verified | `BRAND_IMPLEMENTATION.md`; e2e logo test in both themes (23 Nov) |
| UX | Design system, light and dark themes, command palette, Analyst Lens | Verified | `ui.test.tsx`; ADR-0011 |
| UX | Plan / Procure / Govern navigation, shown per role and tenant data | Verified | `test_planning_sections_follow_role_and_tenant_data`; browser |
| Security | Server-side RBAC, warehouse scope, tenant isolation, cost fields | Verified | security-tagged tests |
| Security | Production identity (OIDC browser flow) | Partial | LA-01 in `SECURITY_AUDIT.md` |
| Operations | Health checks, structured logs, audit trail | Verified | `/api/health`, log tests |
| Operations | Metrics and tracing, backups, restore drill | Missing | `PRODUCTION_READINESS_ASSESSMENT.md` |

## 2. Findings that matter most

1. **The planning gap is closed at engine, API, assistant and web level** for orders, materials, BOM, suppliers and master data. Still missing: capacity, forecasting, a supplier directory page, and FX/charges data.
2. **Branding is done** (23 Nov): official logos integrated byte-identical, theme-aware, verified in both themes.
3. **Production identity and several security findings remain open** (LA-01, LA-06, LA-11, LA-13, LA-20, LA-22). The product is **not production-ready**; see `PRODUCTION_READINESS_ASSESSMENT.md`.
4. **No live ERP connector exists.** Every customer path today is DuckDB, or a file import plus mapping.
5. **Tests:** API 754 passed and 6 skipped; web unit 78 passed. Web lint and typecheck are clean. Browser e2e 29 passed, including the production build (23 Nov).
