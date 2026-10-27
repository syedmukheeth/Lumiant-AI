# Production Readiness Checklist

**Verdict (2026-10-27): NOT production-ready.** The platform is complete and tested on synthetic data with development
authentication, but nothing here has been exercised against a customer system, a customer identity provider, a customer AI
approval, or a production deployment. Items below are marked honestly; "Verified" means proven by an automated test or recorded check.

Legend: **Verified** · **Implemented, unverified** (code exists, cannot be proven here) · **Open** (needs work) · **Blocked** (needs the customer).

## 1. Data and correctness
| Item | Status | Evidence / gap |
|---|---|---|
| Totals equal independent SQL on the physical tables | Verified (synthetic) | `test_query_service.py`, `test_api.py`, `test_m2_analyses.py` |
| Currency and unit safety rails | Verified | validator tests, beta tenant (EUR + GBP) |
| Costing definitions approved by the customer | **Blocked** | D-002, Q-006–Q-008 |
| Reconciliation against the customer's authoritative reports | **Blocked** (tool Verified) | Q-015; `/api/admin/reconciliation` |
| Real schema mapped and drift-checked | **Blocked** | Q-001–Q-003; `/api/admin/schema` |
| Value maps (source codes → canonical values) | Open | ISSUES #3, #15 |
| Performance on customer-sized data | Open | row caps and timeouts exist; no load test (ISSUES #6) |

## 2. Security
| Item | Status | Evidence / gap |
|---|---|---|
| Server-side RBAC, scope, tenant isolation, cost-field control | Verified | security-tagged tests, e2e |
| SQL safety (bound parameters, guard, read-only) | Verified | `test_compiler_and_guard.py`, `test_query_service.py` |
| Dev auth cannot run in production | Verified | `test_config.py` |
| OIDC bearer authentication with group → role/scope mapping | Implemented, unverified against a real IdP | `test_oidc.py` uses local keys; Q-010 |
| Algorithm-confusion and `alg:none` tokens rejected | Verified | `test_oidc.py` |
| Rate limiting (chat, query, export, sign-in) | Verified (single process) | `test_hardening.py`; per-replica memory, no shared store |
| Strict CSP on the web app | Verified, with `'unsafe-inline'` for scripts | e2e CSP test; nonce-based CSP is Open |
| Spreadsheet formula-injection protection, audited exports | Verified | `test_reports.py` |
| AI: grounded numbers, tool permissions, tenant approval gate, disclosure log | Verified (fake external client) | `test_agent.py`; external provider never called live (ISSUES #13) |
| Dependency audits | Verified (2026-10-27, 0 findings) | `pnpm audit`, `pip-audit`; CI will repeat |
| Secret scanning in CI | Open | add a scanner to CI |
| Penetration test / third-party review | Open | recommended before go-live |
| TLS, HSTS, encryption at rest | Open | deployment platform responsibility |

## 3. Operations
| Item | Status | Evidence / gap |
|---|---|---|
| Health endpoints | Verified | `/api/health`, `/api/health/ready` |
| Structured JSON logs with request ids, no secrets or values | Verified | logging design + tests of error bodies |
| Audit trail (allow and deny), explorer, fail-closed writes | Verified | `test_admin.py`, `test_query_service.py` |
| Migrations | Verified on SQLite | Alembic `0001`; PostgreSQL untested |
| PostgreSQL for the app database | Implemented, unverified | `postgres` extra; no local PostgreSQL |
| Container images | Implemented, unverified | `Dockerfile`s written; no Docker available to build them |
| CI pipeline | Implemented, unverified | `.github/workflows/ci.yml` not yet run |
| Metrics / tracing (OpenTelemetry) | Open | logs only |
| Backups, restore drill, rollback rehearsal | Open | see `RUNBOOK.md` |
| Audit/chat retention policy | **Blocked** | Q-014 |

## 4. Product and people
| Item | Status |
|---|---|
| User guide, administrator guide | Written (`USER_GUIDE.md`, `ADMIN_GUIDE.md`) — to be validated with real users |
| Accessibility audit (WCAG) | Open — semantic markup and contrast tokens only |
| Customer sign-off on definitions and AI use | **Blocked** |

## 5. Go-live gates (all must be true)
1. Written authorization and an approved **test** environment (`03-security/SECURITY_PLAN.md` gate).
2. Read-only service account proven by a failing write test.
3. Mapping validated by `/api/admin/schema` with verdict `ok`.
4. Reconciliation passes against the customer's authoritative reports.
5. Customer approves costing and ABC definitions (metrics change from `draft` to `customer-approved`).
6. Customer IdP integrated; group → role/scope mapping signed off; dev auth absent from the image.
7. AI decision recorded (built-in matching only, or an approved provider with data-handling terms).
8. Backups, rollback and incident contacts rehearsed.
