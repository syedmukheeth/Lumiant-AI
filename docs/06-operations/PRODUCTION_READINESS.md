# Production Readiness Checklist

**Verdict (2026-10-27, after cloud verification): NOT production-ready.** The platform is complete and tested on synthetic data with development
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
| Rate limiting (chat, query, export, sign-in) | Verified, incl. shared Redis store | `test_hardening.py`, `test_ratelimit_redis.py` (Redis 7.0.15, two-replica test). Default is per-replica memory; Redis opt-in via `LUMIANT_RATE_LIMIT_REDIS_URL`; outage degrades to per-replica. Not tested on a managed/clustered Redis |
| Strict CSP on the web app | Verified, per-request nonce, no `'unsafe-inline'` for scripts | e2e CSP test (nonce on every inline script, differs per request, no violations on any page); `style-src` still `'unsafe-inline'` (ADR-0007) |
| Spreadsheet formula-injection protection, audited exports | Verified | `test_reports.py` |
| AI: grounded numbers, tool permissions, tenant approval gate, disclosure log | Verified (fake external client) | `test_agent.py`; external provider never called live (ISSUES #13) |
| Dependency audits | Verified (2026-10-27, 0 findings, re-run on Linux incl. postgres/redis extras) | `pnpm audit`, `pip-audit`; CI repeats |
| Secret scanning in CI | Open | add a scanner to CI |
| Penetration test / third-party review | Open | recommended before go-live |
| TLS, HSTS, encryption at rest | Open | deployment platform responsibility |

## 3. Operations
| Item | Status | Evidence / gap |
|---|---|---|
| Health endpoints | Verified | `/api/health`, `/api/health/ready` |
| Structured JSON logs with request ids, no secrets or values | Verified | logging design + tests of error bodies |
| Audit trail (allow and deny), explorer, fail-closed writes | Verified | `test_admin.py`, `test_query_service.py` |
| Migrations | Verified on SQLite and PostgreSQL 16 | Alembic `0001` up/down/up; `test_audit_store.py` |
| PostgreSQL for the app database | Verified on PostgreSQL 16 (self-hosted, apt) | whole API suite (275 tests) passes with `LUMIANT_TEST_PG_ADMIN_URL`; not tried on a managed service or other versions |
| Container images | Built and run, with caveats | Both images built; compose stack ran; sign-in and overview verified in a browser; API container runs as uid 10001, healthcheck passes. One real bug found and fixed. **Caveat:** built here with stand-in base images (ghcr.io blocked, Docker Hub rate-limited — TEST_RUNS CV-2), the CI `docker` job has since built both images from the real upstream images and passed the compose smoke test (TEST_RUNS S02-2). Production-mode container (OIDC, PostgreSQL) was only checked to refuse to start without config |
| CI pipeline | Verified on GitHub Actions | Run on `3ef74b9`: `api`, `api-postgres-redis`, `web`, `docker` (real upstream images + compose smoke) and `e2e` all green. The first run had failed at mypy (ISSUES #22) |
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
