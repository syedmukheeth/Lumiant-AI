# API Contracts

Status: **Implemented and tested (M1)** in `services/api/src/lumiant/api/`. Base path `/api`. JSON only. Live schema: `/api/docs` (development only).

## Conventions

- Auth: development mode uses the httpOnly cookie `lumiant_session`; OIDC mode expects `Authorization: Bearer <IdP token>` (the cookie is ignored). Rate-limited endpoints return 429 `rate_limited` with `Retry-After`. State-changing requests must send header `X-Requested-With: lumiant` (CSRF defence alongside SameSite=Lax).
- Decimals (quantities, prices, values) are **strings** (`"1234.5600"`). Dates ISO-8601; timestamps UTC with `Z`.
- Data responses share one envelope:
```json
{ "data": [ {…} ], "columns": [{"name": "value", "type": "decimal"}],
  "provenance": { … see QUERY_ENGINE.md §6 … }, "warnings": [{"code": "stale_data", "message": "…"}],
  "page": {"offset": 0, "limit": 50, "total": 1234} }
```
- Errors: `{ "error": { "code": "forbidden_scope", "message": "…safe text…", "request_id": "…" } }` with 400/401/403/404/409/422/500/502/503/504. Validation errors (422) list field locations and error types only, never the submitted value.
- Every response carries `X-Request-ID` and security headers (`nosniff`, frame `DENY`, `no-referrer`, `no-store`, restrictive CSP).
- Error codes in use: `not_authenticated`, `forbidden`, `forbidden_field`, `forbidden_scope`, `csrf_failed`, `dataset_not_available`, `field_not_available`, `join_not_allowed`, `invalid_dimension`, `invalid_aggregation`, `invalid_filter`, `invalid_value`, `invalid_having`, `invalid_order`, `limit_exceeded`, `query_rejected` (SQL guard), `analysis_unavailable`, `metric_not_found`, `source_unavailable` (503), `query_timeout` (504), `query_failed` (502), `audit_unavailable` (503), `invalid_request` (422), `internal_error` (500).

## Endpoints (M1)

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/api/health` | none | liveness `{status:"ok"}` |
| GET | `/api/health/ready` | none | tenants loaded, connectors reachable (no details leaked) |
| GET | `/api/auth/dev-users` | none (dev mode only, 404 otherwise) | list dev users for login picker |
| POST | `/api/auth/dev-login` | none (dev mode only) | `{username}` → sets cookie, returns `me` |
| POST | `/api/auth/logout` | session | clears cookie |
| GET | `/api/auth/me` | session | user, tenant, roles, permissions, scope summary, nav sections |
| GET | `/api/meta/tenant` | session | display name, source system, synthetic flag, data as-of, stale flag, non-secret policies, freshness warnings |
| GET | `/api/metrics` | `dashboard:read` | metric catalog entries visible to the user |
| GET | `/api/metrics/{metric_id}` | `dashboard:read` (+ metric perms) | metric result envelope |
| GET | `/api/inventory/filters` | `inventory:read` | scoped options, sorted: warehouses, item groups, ABC, stages, stock statuses, each up to `max_rows`; `truncated` names the lists that hold more values, `limit` is the cap (V0) |
| GET | `/api/inventory/balances` | `inventory:read` | paginated stock lines; query: `warehouse`, `item_group`, `abc`, `stage` (repeatable), `q` (≤ 100 chars; code / description / id), `sort` (`item_code`, `description`, `item_group`, `abc_class`, `warehouse`, `quantity`, `value`), `dir`, `offset`, `limit` (≤ 200). Cost columns only with `cost:read`; `page.total` included |
| GET | `/api/analyses/below-reorder` | `inventory:read` | items under reorder level in scope; same filters as balances plus `offset`/`limit`; `summary {flagged, pairs_without_policy, uom_mismatched_lines}` |
| GET | `/api/analyses/excess-stock` | `inventory:read` | on hand above customer maximum; same envelope as below-reorder |
| GET | `/api/analyses/dormant` | `inventory:read` | `days` (1–3650, default 270); stock with no ISSUE in that window |
| GET | `/api/analyses/expiring-lots` | `inventory:read` | `days` (0–3650, default 60); expired and expiring lots on hand. `summary.expired` and `summary.expiring` count stock lines and `summary.expired_lots` / `summary.expiring_lots` count lots (each item and lot once), all in the source, so `limit` caps the listing only (V0, ISSUES #45) |
| GET | `/api/insights` | `inventory:read` | `fresh` (bool, also bypasses the shared analysis cache) → `{insights[], gaps[], failed[], complete, generated_at, data_as_of, warnings[]}`. `warnings` carries `stale_data` / `unknown_freshness`, read fresh even when the feed is cached (ISSUES #47). `gaps`: data not mapped. `failed` (`{id, label, code, message}`): a check that could not run. `complete` is false when anything failed; such a feed is never cached and must not be read as "nothing to report" |
| GET | `/api/analyses/data-quality` | `inventory:read` | list of checks with status/count/examples (value checks need `cost:read`) |
| GET | `/api/analyses/abc` | `inventory:read` + `cost:read` | `a`, `b` cutoffs required (no defaults), optional `currency`; 409 `abc_mixed_currency` if several |
| GET | `/api/analyses/cost-comparison` | `inventory:read` + `cost:read` | `item_id`, `warehouse_id`; MWA, FIFO, latest receipt cost, latest valid purchase price, source valuation, reconciliation, lots |
| GET | `/api/reports` | `inventory:read` | reports visible to the user + `can_export` |
| GET | `/api/reports/{id}` | `inventory:read` (+ report permissions) | preview (≤ 200 rows) with `metadata`; `days` for windowed reports |
| GET | `/api/reports/{id}/export` | `inventory:read` + `export:data` | `format=csv\|xlsx`; attachment with metadata header |
| GET | `/api/admin/schema` | `admin:tenant` | mapping vs source: drift, unmapped columns, health; `unconfigured_warehouses`: warehouses in the stock data but not in the tenant configuration (verdict becomes drift, ISSUES #46) |
| GET | `/api/admin/source` | `admin:tenant` | current source: kind, engine, health, `data_as_of`, `stale`, rows per mapped dataset (V1) |
| POST | `/api/admin/source/test` | `admin:tenant` + CSRF | body `{url}`: connect read-only, privilege check (`read_only.status` proved / writable / not_checked), tables and views (first 300). The URL is used once: never stored, logged or returned. SQLite only outside production (V1) |
| POST | `/api/admin/source/suggest` | `admin:tenant` + CSRF | body `{url}`: mapping suggestions for an unconfigured source (names only) (V2) |
| GET | `/api/admin/mapping/suggest` | `admin:tenant` | suggestions for the current source with `current_source` / `agrees` per dataset, and a YAML draft (V2) |
| GET | `/api/admin/validation` | `admin:tenant` | `{passed, checks[]}`: key uniqueness, orphans, missing required values; counts only (V2) |
| GET | `/api/admin/api-keys` | `admin:tenant` | `{keys[], grantable[]}`: name, rights, warehouses, created / last used, revoked; never the secret (V3) |
| POST | `/api/admin/api-keys` | `admin:tenant` + CSRF | body `{name, permissions[], warehouses?}` → `{key, record}`; the key is shown once; rights ⊆ creator and grantable set, warehouses ⊆ creator scope (V3) |
| DELETE | `/api/admin/api-keys/{id}` | `admin:tenant` + CSRF | revoke (V3) |
| POST | `/mcp` | API key (`Authorization: Bearer lmk_...`) | Model Context Protocol (JSON-RPC 2.0): `initialize`, `ping`, `tools/list`, `tools/call`; tools = permitted analyses + `ask_lumiant`; see `06-operations/INTEGRATIONS.md` (V3) |
| GET | `/api/admin/capabilities` | `admin:tenant` | capability matrix with missing fields |
| GET | `/api/admin/audit` | `audit:read` | tenant's audit events; filters `decision`, `action` prefix |
| POST | `/api/admin/reconciliation` | `admin:tenant` + `cost:read` | `{tolerance, rows[{warehouse_id,currency,value}]}` → per-line status + `passed` |
| GET | `/api/agent/suggestions` | `chat:use` | starter questions |
| POST | `/api/agent/chat` | `chat:use` | `{message}` (2–500 chars) → `{mode, notice, kind (tools/clarify/unsupported), answer, blocks[], tool_calls[], provenance[], warnings[], follow_ups[], choices[], grounding}`. `grounding.passed` false means figures could not be verified; `grounding.source` `blocked` means model text was withheld and `answer` is a fixed notice |
| POST | `/api/agent/feedback` | `chat:use` | `{rating: up/down, reason?}` recorded in the audit trail |
| POST | `/api/query` | `query:run` | body = QueryPlan → envelope |

Exact request/response models: FastAPI OpenAPI at `/api/docs` (enabled only when `APP_ENV != production`).

## Public: demo requests (Product v2, S10)
- `POST /api/public/demo-requests`: no session; needs the CSRF header; per-IP rate limit (login bucket). Body: `name` (1–120), `email` (work email), `company` (1–160), optional `role`, `systems`, `message` (≤ 1000), `consent: true`, hidden `website` (honeypot: accepted, not stored). `202 {"status": "received"}`; `422` for invalid input or no consent. Stored in the application database (`demo_request`, Alembic `0002`); personal details are never logged.
- `GET /api/admin/demo-requests`: `super_admin` only (platform data, not tenant data); latest 100.

## Agent tools added in S10 (ADR-0012)
- `query_inventory`: typed plan over the canonical catalog (dataset, group_by, measures, filters, order_by, descending, limit ≤ 100); same validation, scope and audit as `/api/query`.
- `search_knowledge`: cited passages from Lumiant's definitions; answer blocks gain `{"type": "sources", "title", "items": [{id, source, heading, text}]}`.
- Stream steps `think:N` ("Reviewing the results") appear between tool rounds when an external model plans several rounds.
