# Milestone 1 — Foundation, synthetic data, canonical model, first dashboard

Approved 2026-10-26 (session 01). Execution started the same session.

## Goal
A running, documented dev environment where authenticated (dev-mode) users of two synthetic tenants see a trustworthy overview dashboard and inventory explorer, backed by a tested, secured, read-only query core. No AI yet.

## In scope
1. Knowledge base + logging protocol (`docs/`, `CLAUDE.md`, `AGENTS.md`).
2. Dependency spike (DuckDB 1.5 + duckdb-engine + SQLAlchemy 2.0).
3. API core: settings/env validation, JSON logging, error model, request context, tenant registry, canonical catalog, mapping resolver.
4. Synthetic generator (2 tenants with different physical schemas, planted scenarios) + CLI.
5. DuckDB connector (read-only, timeout, row cap), QueryPlan, validator, compiler, sql_guard, executor, provenance, audit store (SQLite + Alembic).
6. Dev auth + RBAC + scope; routes: health, auth, meta, metrics, inventory, below-reorder, query.
7. Next.js app: login, shell, overview, inventory.
8. Tests: unit, integration (incl. independent raw-SQL checks), security, web unit, e2e.

## Exit criteria
- [x] `uv run pytest` passes (134); `ruff` and `mypy` clean
- [x] `pnpm lint`, `pnpm typecheck`, `pnpm test` pass (20); Playwright e2e passes (5)
- [x] Overview totals equal independent raw SQL on physical tables (test)
- [x] Users cannot see other tenants, out-of-scope warehouses, or cost fields without permission (tests)
- [x] Dev auth refuses to start in production config (test)
- [x] Synthetic badge and data as-of visible in the UI (e2e + browser check)
- [x] Docs match the code; `CURRENT_STATE.md` rewritten; logs complete

## Out of scope (state this honestly)
LLM/chat, costing engine, computed ABC, risk analyses other than below-reorder, exports, OIDC, Postgres app-DB testing, real connectors, deployment.
