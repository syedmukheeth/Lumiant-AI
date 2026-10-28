# Decision Log

One line per decision. Details in the linked ADR.

| Date | ID | Decision | ADR |
|---|---|---|---|
| 2026-10-26 | DEC-001 | Modular monolith: FastAPI backend + Next.js frontend, no microservices | [ADR-0001](../02-architecture/adr/0001-modular-monolith-fastapi-nextjs.md) |
| 2026-10-26 | DEC-002 | The LLM never writes SQL or computes authoritative numbers; typed tools only | [ADR-0002](../02-architecture/adr/0002-llm-never-writes-sql.md) |
| 2026-10-26 | DEC-003 | DuckDB files (read-only) as the synthetic customer warehouse | [ADR-0003](../02-architecture/adr/0003-duckdb-synthetic-warehouse.md) |
| 2026-10-26 | DEC-004 | Dev-only auth (signed cookie) with a hard production guard; OIDC later | [ADR-0004](../02-architecture/adr/0004-dev-only-auth.md) |
| 2026-10-26 | DEC-005 | Pin TS 5.9.3, DuckDB 1.5.x, SQLAlchemy 2.0.x (spike to confirm) | [ADR-0005](../02-architecture/adr/0005-conservative-version-pins.md) |
| 2026-10-26 | DEC-006 | Tenant configuration as validated YAML in the repo | [ADR-0006](../02-architecture/adr/0006-tenant-config-as-code.md) |
| 2026-10-26 | DEC-007 | Keep the full knowledge base and per-step logs in `docs/` (owner instruction) | — (`00-context/CONTEXT_FLOW.md` §B) |
| 2026-10-27 | DEC-008 | LIKE escape character is `!` (backslash is mis-rendered for DuckDB by the PG dialect) | [ADR-0005 spike](../02-architecture/adr/0005-conservative-version-pins.md) |
| 2026-10-27 | DEC-009 | Decimal outputs bypass SQLAlchemy result processing (`ExactDecimal`) so values are exactly what the DB computed | `02-architecture/QUERY_ENGINE.md` §3 |
| 2026-10-27 | DEC-010 | Explicit filters on out-of-scope warehouses return 403 (not an empty result); scope is still injected for every query | `02-architecture/QUERY_ENGINE.md` §2 |
| 2026-10-27 | DEC-011 | Web fetches data client-side through the same-origin `/api` proxy; no server component reads cookies | `02-architecture/FRONTEND.md` |
| 2026-10-27 | DEC-012 | Audit writes fail closed (no audit row → no data returned) | `02-architecture/QUERY_ENGINE.md` §7 |
| 2026-10-27 | DEC-013 | Keep pnpm's minimum-release-age gate; pin older versions instead of adding exclusions | `00-context/ENVIRONMENT.md` |
| 2026-10-27 | DEC-014 | Nonce-based CSP with per-request rendering (`cacheComponents` off); optional Redis shared rate-limit store with in-process fallback | `02-architecture/adr/0007-nonce-csp-and-shared-rate-limit.md` |
| 2026-10-27 | DEC-015 | Real client extracts are local-only, classified `customer_extract` (private tenant dir, `var/private/`, dev + flag, production refusal, CONFIDENTIAL labels, external AI off) | [ADR-0008](../02-architecture/adr/0008-client-extracts-local-only.md) |
| 2026-10-27 | DEC-016 | Value maps compile to CASE with constants rendered inline (validated config) so SELECT/GROUP BY/ORDER BY text is identical; NULL stays NULL, unknown codes read `unmapped`; keys cannot be value-mapped | `02-architecture/MAPPING.md` |
| 2026-10-27 | DEC-017 | Plant-level SAP master fields (ABC, MRP type, price control, price) go to a new canonical dataset `item_warehouse`, not to `item` | `02-architecture/DATA_MODEL.md` |
| 2026-10-27 | DEC-018 | SAP total rows are control totals: the import aborts unless detail rows add up exactly per unit and value column; split valuation and inexact price units are refused/unpriced, never guessed | `07-customer/CLIENT_DATA_INTAKE.md` §4 |
