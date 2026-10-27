# Testing

Testing is part of every step (brief §18). Every run is recorded in `../logs/TEST_RUNS.md`. Never weaken a test to make code pass.

## Suites and how to run them

| Suite | Where | Command | Count (2026-10-27) |
|---|---|---|---|
| API unit | `services/api/tests/unit` | `uv run pytest -q tests/unit` | part of 134 |
| API integration (generated warehouses) | `services/api/tests/integration` | `uv run pytest -q -m integration` | part of 134 |
| API security-tagged | both | `uv run pytest -q -m security` | subset |
| API lint / format / types | | `uv run ruff check .` · `uv run ruff format --check .` · `uv run mypy` (strict) | clean |
| Web unit (Vitest + Testing Library) | `apps/web/tests/unit` | `pnpm test` | 20 |
| Web lint / types | | `pnpm lint` · `pnpm typecheck` | clean |
| End-to-end (Playwright, Chromium) | `apps/web/e2e` | `pnpm exec playwright install chromium` once, then `pnpm e2e` | 5 |
| Dependency audit | | `pnpm audit` (web) · `uv export --no-hashes --format requirements-txt --no-emit-project > req.txt && uvx pip-audit -r req.txt` (API) | 0 known vulns |
| Everything except e2e | repo root | `pnpm run check` | |

## What each layer proves

| Area | Tests | Key assertions |
|---|---|---|
| Config guard | `test_config.py` | dev auth refused in production; production needs secure cookies; weak secrets rejected |
| Tenant config | `test_tenancy.py` | unknown keys, unmapped required fields, computed-field mapping, injection in identifiers, path traversal, customer tenants can't have dev users |
| Mapping | `test_mapping.py` | canonical → physical resolution, computed fields, attributes, schema-qualified sources |
| Synthetic data | `test_synthetic.py` | determinism; **balances = Σ movements** (both schemas, raw SQL); no negative running balances; referential integrity; join-key uniqueness; planted scenarios; DECIMAL types |
| Validator | `test_validator.py` | every rejection code; cost fields blocked in select/filter/aggregate/any-of; scope injection; explicit out-of-scope → 403; negative filters can't widen scope; currency/UoM companions |
| Compiler + guard | `test_compiler_and_guard.py` | values are bound parameters (incl. scope); escaped LIKE; limit+1; guard rejects DML/DDL, multi-statement, system tables, table functions, unions, unmapped tables |
| Query service | `test_query_service.py` | totals equal **independent raw SQL** (alpha + beta per currency); scope; tenant isolation; truncation + totals; injection strings are data; provenance contents; audited denials without values; DB-level read-only; timeout interrupt; missing source |
| HTTP API | `test_api.py` | cookie flags; CSRF; forged/expired/none-alg/cross-tenant tokens; no-cost user; scope 403s; tenant isolation; below-reorder vs raw SQL incl. zero-stock pairs; safe error bodies; OIDC mode refuses to start |
| Audit store | `test_audit_store.py` | first run creates the folder and schema |
| Web formatting | `format.test.ts` | exact decimal-string formatting (no float drift), half-even rounding, currency codes always shown, missing values never shown as 0 |
| Web API client | `api.test.ts` | CSRF header, safe error parsing, network errors |
| Provenance UI | `provenance.test.tsx` | mapping, user vs permission filters, SQL only when the API sent it |
| E2E | `e2e/app.spec.ts` | redirect when signed out; admin values + provenance; search/filter/paging (+ debounce regression); analyst never receives values (UI + direct API call 403); other-tenant user sees only own warehouse |

## The e2e stack

`playwright.config.ts` starts an isolated stack: API on **8100** with freshly generated data and its own app DB in `services/api/var/e2e/`, and a **production build** of the web app on **3100**. It does not touch the dev stack on 8000/3000.

## Not yet covered (tracked)

- Real customer databases (none connected — `../02-architecture/CONNECTORS.md`).
- PostgreSQL app DB (no local Postgres — ISSUES #1).
- AI agent tests and eval harness (M3).
- Costing/financial fixtures (M2).
- Load/performance tests (M6/M7).
