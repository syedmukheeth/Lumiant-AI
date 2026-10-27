# Changelog

User-visible changes per milestone. Format loosely follows Keep a Changelog.

## [M1] — 2026-10-27 (not yet committed)
### Added
- Project knowledge base under `docs/` with logging protocol, ADRs 0001–0006, decision log, issue log.
- API service (`services/api`): tenant configuration with startup validation, canonical inventory model, per-tenant mapping, DuckDB read-only connector, secured query engine (validation, scope injection, cost-field control, currency/UoM safety rails, parameterized SQL, SQL guard, timeouts, provenance, audit), 7 draft metrics, below-reorder analysis, development-only authentication with role and warehouse scopes.
- Synthetic data generator for two demo tenants (`lumiant-synthetic generate`).
- Web app (`apps/web`): development sign-in, permission-aware navigation, overview dashboard, inventory explorer, provenance slips, synthetic-data badge, data as-of indicator, light/dark themes, responsive layout.
- Tests: 134 API tests (unit, integration, security), 20 web unit tests, 5 end-to-end tests.

## [M2] — 2026-10-27
### Added
- Costing engine (moving and periodic weighted average, FIFO layers, latest price definitions), computed ABC, configurable item-code rules.
- Analyses: excess stock, dormant stock, expiring lots, master-data quality, cost comparison with reconciliation, computed vs assigned ABC.
- Web: Risks and Costs pages; navigation adapts to cost permission.
- Tests: 177 API, 8 end-to-end.

## [M3] — 2026-10-27
### Added
- Assistant: ask questions in plain language; answers come from checked queries with tables, charts, sources and follow-ups.
- Ten typed analysis tools, clarification when an item or warehouse is ambiguous, honest refusals (e.g. obsolescence prediction).
- Numeric grounding guard, external-AI approval gate per tenant, disclosure and feedback audit records.
- Golden and adversarial evaluation sets; 220 API tests, 11 end-to-end tests.
