# Implementation Plan (checkbox tracker)

Tick an item **only when it is verified** (a test or recorded check). Link evidence in `logs/WORKLOG.md`.
Order follows dependencies. Milestone detail: `ROADMAP.md`, `MILESTONE_01.md`.

## Phase 1 — Investigation & design (brief Phases 1–3)
- [x] Inspect working directory, git status, toolchain (S01)
- [x] Check current package versions on npm/PyPI (S01)
- [x] Project assessment A–J (`00-context/PROJECT_ASSESSMENT.md`)
- [x] Requirements, open questions, architecture, security plan, roadmap
- [x] Knowledge base + logging protocol

## M1 — Foundation
### Step 1 — repo + knowledge base
- [x] `git init` (no commits until the owner asks)
- [x] Knowledge base written (`docs/`)
- [x] `CLAUDE.md`, `AGENTS.md`, `.gitignore`, `.editorconfig`, `.gitattributes` (root `README.md` written at step 8)
### Step 2 — dependency spike
- [x] DuckDB 1.5 + duckdb-engine + SQLAlchemy 2.0: compile, bound params, read_only, interrupt
- [x] Record result in ADR-0005
### Step 3 — API core
- [x] `pyproject.toml`, uv lock, ruff/mypy/pytest config
- [x] Settings + env validation (dev auth refused in production)
- [x] JSON logging, request context, error model (exercised by API tests in step 6)
- [x] Tenant config models + registry + 2 demo tenant YAMLs
- [x] Canonical catalog
- [x] Mapping resolver
### Step 4 — synthetic data
- [x] Generator (deterministic) + scenarios
- [x] Writer using tenant mapping → DuckDB
- [x] CLI `lumiant-synthetic`
- [x] Tests: determinism, balances = Σ txns, no negative lots, scenarios present
### Step 5 — query core
- [x] Connector protocol + DuckDB connector (read-only, timeout, row cap)
- [x] QueryPlan + validator (incl. scope injection, safety rails)
- [x] Compiler + sql_guard + executor + provenance
- [x] Audit store (SQLite + Alembic)
### Step 6 — auth, RBAC, routes
- [x] Dev auth provider, principal, permission deps
- [x] Routes: health, auth, meta, metrics, inventory, below-reorder, query
- [x] Metric catalog
- [x] Integration tests (independent raw SQL)
- [x] Security tests
### Step 7 — web
- [x] Next.js scaffold (TS 5.9, Tailwind 4, lint, vitest, playwright)
- [x] API client + formatters
- [x] Login, shell, overview, inventory
- [x] Vitest + Playwright
### Step 8 — close
- [x] Full check run recorded in TEST_RUNS
- [x] Browser check (desktop + mobile width)
- [x] Docs synced; CURRENT_STATE rewritten; ACCEPTANCE_CRITERIA updated

## M2 — Intelligence engine (next; detailed when started)
- [x] Hand-verified financial fixtures (zero qty, negative stock, duplicates, returns, mixed currency/UoM, period boundaries, rounding)
- [x] Moving weighted average engine + reconciliation against the source valuation price
- [x] Periodic weighted average, FIFO cost layers, lot cost, latest-price definitions (draft)
- [x] Computed vs assigned ABC (caller-supplied cutoffs; period/value definition fixed to on-hand value as a draft)
- [x] Analyses: excess, dormant, expiring lots, master-data quality (ageing and price movement deferred)
- [x] Item-code parser per tenant
- [ ] Value maps in tenant mapping (ISSUES #3) — moved to M5

## M3 – M7
See `ROADMAP.md`. Detailed checklists are added when each milestone starts.
