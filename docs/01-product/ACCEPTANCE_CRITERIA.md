# MVP Acceptance Criteria (brief §23)

The MVP is **not** complete until every row is *Verified* with linked evidence. A green build or a polished UI is not evidence.
Status as of 2026-10-27 (end of M1). "Verified (synthetic)" = proven on generated data only.

| # | Criterion | Target M | Status | Evidence |
|---|---|---|---|---|
| 1 | App starts reliably in a documented dev environment | M1 | **Verified** | `06-operations/DEV_SETUP.md`; first-run bug fixed + `test_audit_store.py`; e2e starts a fresh stack each run |
| 2 | Users authenticate via approved dev or customer mechanism | M1 (dev) / M6 (IdP) | **Verified (dev only)** | `test_api.py` auth tests; customer IdP blocked (Q-010) |
| 3 | Backend authorization enforced | M1 | **Verified** | `test_api.py` (401/403 cases), `test_validator.py` scope + cost tests |
| 4 | Synthetic inventory data available | M1 | **Verified** | `lumiant-synthetic`, `test_synthetic.py` |
| 5 | Inventory records can be filtered and viewed | M1 | **Verified (synthetic)** | `/api/inventory/balances`, e2e `inventory search, filters and paging` |
| 6 | Warehouse-level summaries can be calculated | M1 | **Verified (synthetic)** | `inventory_value_by_warehouse` vs raw SQL tests |
| 7 | ABC classifications follow configurable, tested rules | M2 | **Verified (synthetic, draft method)** | `test_costing.py::test_abc_*`, `test_m2_analyses.py::test_abc_*` |
| 8 | Cost comparisons use documented calculations | M2 | **Verified (synthetic, draft definitions)** | `test_costing.py` hand-computed cases, `test_cost_comparison_reconciles_with_source_valuation` |
| 9 | Chat supports a defined set of inventory questions | M3 | Not started (designed: `01-product/AGENT_DESIGN.md`) | M3 |
| 10 | Queries execute only against approved datasets | M1 | **Verified** | validator `dataset_not_available`/`join_not_allowed`, SQL guard tests |
| 11 | Unauthorized data requests are rejected | M1 | **Verified** | scope/cost/tenant tests (API + e2e) |
| 12 | Missing data produces an honest, useful response | M1 (dashboard) / M3 (chat) | **Verified for M1 scope** | missing valuation price warning, no-policy counts, UoM mismatch warning, `analysis_unavailable`, stale/unknown freshness warnings |
| 13 | Results displayed as tables and appropriate charts | M1 | **Verified (synthetic)** | overview + inventory pages, e2e |
| 14 | Provenance and timestamps visible where relevant | M1 | **Verified** | provenance slip (unit + e2e), data as-of in header |
| 15 | Relevant automated tests pass | every M | **Verified for M1** | `logs/TEST_RUNS.md` (134 API, 20 web unit, 5 e2e) |
| 16 | Security risks and limitations documented | M1+ | **Verified for M1** | `03-security/*`, `logs/ISSUES.md` |
| 17 | Setup and deployment instructions exist | M1 (setup) / M6 (deploy) | Setup **verified**; deployment not started | `06-operations/DEV_SETUP.md`, `DEPLOYMENT.md` (draft) |
| 18 | Team can explain implemented vs simulated vs customer-dependent | every M | **Verified for M1** | `00-context/CURRENT_STATE.md` |
