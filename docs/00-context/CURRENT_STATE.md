# Current State

_Rewritten at the end of every session. Last update: 2026-10-28, S03 (M8 client SAP data intake; uncommitted on branch `claude/frosty-almeida-6aaddf`)._

## Milestone
**M1 (foundation), M2 (intelligence engine), M3 (AI agent) M4 (reports, exports, guided menu) and most of M5 (schema drift check, capability matrix, reconciliation gate, audit explorer) complete on synthetic data.** Code is on GitHub (`syedmukheeth/Lumiant-AI`, `main`).
**Next:** nothing further can be completed without the customer: M7 needs the answers in `../07-customer/OPEN_QUESTIONS.md`. See `../06-operations/PRODUCTION_READINESS.md` for what is verified and what is not.

## M8 — client SAP data intake (S03, synthetic twin verified; real files loaded locally only)
- `lumiant-ingest sap` loads the client's two SAP exports (MB52-style stock list + material master) into a git-ignored DuckDB under `services/api/var/private/` with a hard control-total gate; the real import passed it. Tenant class `customer_extract` (ADR-0008): dev only, needs `LUMIANT_PRIVATE_TENANTS_DIR` + `LUMIANT_ALLOW_CUSTOMER_EXTRACTS=true`, CONFIDENTIAL badge/exports, external AI off. Structure and checks: `../07-customer/CLIENT_DATA_INTAKE.md`; questions Q-019…Q-026.
- Synthetic twin `demo-gamma` (same importer, planted anomalies), value maps (ISSUES #3 closed), stock status, source-vs-computed value reconciliation (price-rounding aware), SAP data-quality checks, capability "needs file".
- Not done: assistant tools for SAP tenants (#29), plant-level ABC tile (#28), client meanings of codes (#25), movements/reorder/batch files (Q-025).

## What works (verified by automated tests and manual browser checks)

| Capability | Evidence |
|---|---|
| Two synthetic tenants generated deterministically into DuckDB (alpha: SAP-style, USD; beta: snake_case `inv` schema, EUR + GBP) | `tests/unit/test_synthetic.py` |
| Tenant config + canonical model + mapping, validated at startup | `test_tenancy.py`, `test_mapping.py` |
| Query engine: plan validation, scope injection, cost-field control, currency/UoM rails, parameterized SQL, sqlglot guard, read-only DuckDB, timeouts, provenance, audit | `test_validator.py`, `test_compiler_and_guard.py`, `test_query_service.py` |
| Totals equal independent raw SQL on the physical tables | `test_alpha_value_matches_independent_sql`, `test_beta_value_matches_independent_sql_per_currency`, `test_value_by_warehouse_matches_raw_sql` |
| Dev-only auth (signed httpOnly cookie), RBAC, warehouse scope, tenant isolation, CSRF header, safe errors | `tests/integration/test_api.py` |
| Below-reorder analysis incl. zero-stock pairs | `test_below_reorder_matches_independent_sql` |
| Web: login, permission-aware shell, overview, inventory explorer, provenance slips, synthetic badge, data as-of, light/dark, mobile | `apps/web/tests/unit`, `apps/web/e2e/app.spec.ts`, browser checks in WORKLOG M1-step-7 |
| M2: costing (MWA/periodic/FIFO/latest price), computed ABC, item-code rules, excess/dormant/expiry/data-quality, cost comparison reconciled to the source | `test_costing.py`, `test_m2_analyses.py`, e2e `risks`/`costs` |
| M3: assistant with 10 typed tools, grounding guard, permission-filtered tools, clarification, honest refusals, golden + adversarial evals | `test_agent.py`, `evals/*.yaml`, e2e `assistant` |
| M4: six reports, CSV/Excel export with metadata and `export:data`, print view, guided menu | `test_reports.py`, e2e `guided menu`, `reduced role` |
| M5: schema drift detection, capability matrix, reconciliation gate, audit explorer | `test_admin.py`, e2e `admin` |
| M6: rate limits, OIDC bearer auth (local keys), strict CSP | `test_hardening.py`, `test_oidc.py`, e2e CSP test |
| Cloud verification (Linux) | API 269 passed + 6 env-gated skipped (**275 pass** with PostgreSQL 16 + Redis 7) · web unit 23 · e2e 16 · ruff/mypy strict/eslint/tsc clean · audits 0 findings — `../logs/TEST_RUNS.md` CV-1…CV-6 |
| Containers | API and web images built, compose demo ran, sign-in + overview verified in a browser; bug fixed (non-root data dir). Built with stand-in base images (registries restricted) |
| PostgreSQL 16 app DB | Alembic up/down/up + whole API suite (`LUMIANT_TEST_PG_ADMIN_URL`) |
| Shared rate limit | Optional Redis store (`LUMIANT_RATE_LIMIT_REDIS_URL`), tested on Redis 7.0; in-process default and outage fallback |
| Nonce CSP | Per-request nonce, no `'unsafe-inline'` scripts; e2e-verified (ADR-0007) |

## What is simulated (not evidence of customer readiness)
- **All data is synthetic.** Valuation price = the generator's own moving average; ABC classes and reorder policies are synthetic stand-ins for customer master data.
- **CI runs green on GitHub Actions** (all five jobs on `3ef74b9`, incl. e2e and the Docker build on real upstream images).
- **Authentication is development-only in practice.** OIDC is implemented and tested with locally generated keys, never against a real identity provider (Q-010). The API refuses dev auth in production.
- **The external AI provider has never been called.** Only the built-in matcher is verified; the Anthropic adapter is tested with a fake client (ISSUES #13).
- **The only connector is DuckDB.** No PostgreSQL, SQL Server, Oracle or SAP connector exists or has been tested.

## Not built yet
LIFO rule, ageing buckets, price-movement alerts, value maps · editable query chips, glossary, capability matrix · drill-through, saved views, background reports · value maps, mapping editor/approval, profiling (rest of M5) · a real IdP; managed PostgreSQL/Redis · real customer integration (M7).

## Known limitations
See `../logs/ISSUES.md` (open: #1 no enterprise warehouse connectors, #2 conservative pins, #3 no value maps, #5 master data tenant-wide, #6 no cost-based query limits, #8 test-client deprecation, #10 animations pause in background tabs, #13 live AI provider, #14, #15, #16 real IdP).

## Blocked on the customer
Everything production-related: `../07-customer/OPEN_QUESTIONS.md` — highest priority Q-001 (warehouse technology/access), Q-003 (schema), Q-006–Q-008 (costing policy), Q-010 (IdP), Q-012 (hosting), Q-013 (AI provider approval).

## Next step
1. CI is green on `main` (`3ef74b9`). Delete the stale `cloud-verify` remote branch when convenient (it points at `f437fdf`, already in `main`).
2. Send Q-001 … Q-017 to Lumiant/the customer (`../07-customer/OPEN_QUESTIONS.md`); M7 cannot start without them.
3. Optional without the customer: value maps and mapping editor (ISSUES #3, #15), non-nonce CSP leftovers (`style-src`), a live-API check of the Anthropic adapter once a key and approval exist.

## How to run
`docs/06-operations/DEV_SETUP.md` (setup) · `docs/06-operations/TESTING.md` (tests).
