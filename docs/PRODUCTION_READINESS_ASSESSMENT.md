# Production Readiness Assessment

**Verdict (23 Nov 2026): NOT production-ready.** Functionality, branding and test coverage are strong on synthetic data. Production identity is not verified against a real IdP, rate limiting is incomplete, and backups, monitoring and load tests are not proven. A successful build is not proof of readiness. This extends `06-operations/PRODUCTION_READINESS.md`, which is still valid.

**Statuses**
- **Passed and verified**
- **Implemented but unverified**
- **Partially implemented**
- **Failed**
- **Blocked by external dependency**

| Criterion | Status | Evidence |
|---|---|---|
| Production authentication works | **Implemented but unverified / Blocked** | API OIDC validation (`test_oidc.py`); web OIDC routing fixed (`proxy.ts`, `tests/unit/proxy.test.ts`); needs the customer IdP and gateway (`PRODUCTION_AUTHENTICATION.md`) |
| Backend authorization complete | **Partially implemented** | Tenant, warehouse, module, dataset and cost-field enforcement verified (`FINE_GRAINED_RBAC.md`); master-data scope and extra sensitivity classes missing (LA-13) |
| Tenant isolation verified | **Passed and verified** | isolation and security-tagged tests; `test_other_tenants_are_untouched` |
| Supplier confidentiality protected | **Passed and verified** (cost-gated within a tenant) | `test_supplier_prices_need_cost_access`; no supplier-facing access exists |
| API rate limiting comprehensive | **Partially implemented** | chat, query, export, login and **planning (new, tested)**; inventory, reports, metrics, insights still open (LA-11) |
| Credentials secure | **Passed and verified** (repository) / **Blocked** (production secret manager) | no `.env` in git; shareable env file without secrets |
| Query access controlled | **Passed and verified** | validator, SQL guard, read-only connectors, row caps, timeouts |
| Data sources validated | **Partially implemented** | schema drift check, reconciliation tool; real customer source not connected (blocked) |
| Source provenance available | **Passed and verified** | provenance on every query result; planning issues and explanations |
| Error handling robust | **Passed and verified** | safe error bodies with request ids; 409 "needs more data" pattern |
| Monitoring exists | **Partially implemented** | structured logs, request ids, health checks, audit; no metrics or tracing (`OBSERVABILITY_AND_OPERATIONS.md`) |
| Backup and recovery tested | **Failed (not tested)** | policy and procedure only (`BACKUP_AND_RECOVERY.md`) |
| Critical browser workflows tested | **Passed and verified** | e2e full run 36/36 with a production build, incl. planning, commitment protection, branding (logo size) and role tests (`e2e/planning.spec.ts`) |
| Performance measured | **Partially implemented** | engine benchmark with fixes (`PERFORMANCE_AND_LOAD_TESTING.md`); no HTTP load test; loader not optimised for millions of rows |
| Deployment rollback documented | **Partially implemented** | runbook outline; no deployment performed |
| Security review complete | **Partially implemented** | engineering reviews (`SECURITY_AUDIT.md`, `ENTERPRISE_SECURITY_REVIEW.md`, `API_SECURITY_REVIEW.md`); no penetration test |
| Critical findings resolved or accepted | **Failed** | LA-01 P0 fixed in code but unverified; P1 items open (`PRODUCTION_HARDENING_PLAN.md`) |
| Customer commitment protection | **Passed and verified** (synthetic data) | scenario harness C-P…C-R, integration and e2e tests; cost-gated and audited; production capacity not modelled (`CUSTOMER_REVENUE_PROTECTION.md`) |
| Official branding | **Passed and verified** | `BRAND_IMPLEMENTATION.md`; e2e logo test in both themes |

## Test evidence (23 Nov 2026, Windows)

| Suite | Result |
|---|---|
| API (pytest) | 786 passed, 6 skipped (Redis/Postgres-gated) |
| Lint and types | ruff, ruff format, mypy strict clean; web eslint and tsc clean |
| Web unit (vitest) | 80 passed |
| Browser (Playwright, incl. production build) | full run 36 passed, 0 failed |
| Planning scenario harness | 90 checks passed, incl. combined P, Q, R (part of the API suite) |

**Compliance:** no regulatory compliance or certification is claimed. Saudi PDPL, data residency and DPAs need legal review (`ENTERPRISE_SECURITY_REVIEW.md` §4).
