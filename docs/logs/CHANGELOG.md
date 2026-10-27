# Changelog

User-visible changes per milestone. Format loosely follows Keep a Changelog.

## [M1] — 2026-10-27 (not yet committed)
### Added
- Project knowledge base under `docs/` with logging protocol, ADRs 0001–0006, decision log, issue log.
- API service (`services/api`): tenant configuration with startup validation, canonical inventory model, per-tenant mapping, DuckDB read-only connector, secured query engine (validation, scope injection, cost-field control, currency/UoM safety rails, parameterized SQL, SQL guard, timeouts, provenance, audit), 7 draft metrics, below-reorder analysis, development-only authentication with role and warehouse scopes.
- Synthetic data generator for two demo tenants (`lumiant-synthetic generate`).
- Web app (`apps/web`): development sign-in, permission-aware navigation, overview dashboard, inventory explorer, provenance slips, synthetic-data badge, data as-of indicator, light/dark themes, responsive layout.
- Tests: 134 API tests (unit, integration, security), 20 web unit tests, 5 end-to-end tests.
