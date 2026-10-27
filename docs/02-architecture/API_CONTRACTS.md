# API Contracts

Status: **Implemented and tested (M1)** in `services/api/src/lumiant/api/`. Base path `/api`. JSON only. Live schema: `/api/docs` (development only).

## Conventions

- Auth: httpOnly cookie `lumiant_session` (dev provider). State-changing requests must send header `X-Requested-With: lumiant` (CSRF defence alongside SameSite=Lax).
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
| GET | `/api/inventory/filters` | `inventory:read` | scoped options: warehouses, item groups, ABC, stages |
| GET | `/api/inventory/balances` | `inventory:read` | paginated stock lines; query: `warehouse`, `item_group`, `abc`, `stage` (repeatable), `q` (≤ 100 chars; code / description / id), `sort` (`item_code`, `description`, `item_group`, `abc_class`, `warehouse`, `quantity`, `value`), `dir`, `offset`, `limit` (≤ 200). Cost columns only with `cost:read`; `page.total` included |
| GET | `/api/analyses/below-reorder` | `inventory:read` | items under reorder level in scope; same filters as balances plus `offset`/`limit`; `summary {flagged, pairs_without_policy, uom_mismatched_lines}` |
| GET | `/api/analyses/excess-stock` | `inventory:read` | on hand above customer maximum; same envelope as below-reorder |
| GET | `/api/analyses/dormant` | `inventory:read` | `days` (1–3650, default 270); stock with no ISSUE in that window |
| GET | `/api/analyses/expiring-lots` | `inventory:read` | `days` (0–3650, default 60); expired and expiring lots on hand |
| GET | `/api/analyses/data-quality` | `inventory:read` | list of checks with status/count/examples (value checks need `cost:read`) |
| GET | `/api/analyses/abc` | `inventory:read` + `cost:read` | `a`, `b` cutoffs required (no defaults), optional `currency`; 409 `abc_mixed_currency` if several |
| GET | `/api/analyses/cost-comparison` | `inventory:read` + `cost:read` | `item_id`, `warehouse_id`; MWA, FIFO, latest receipt cost, latest valid purchase price, source valuation, reconciliation, lots |
| GET | `/api/reports` | `inventory:read` | reports visible to the user + `can_export` |
| GET | `/api/reports/{id}` | `inventory:read` (+ report permissions) | preview (≤ 200 rows) with `metadata`; `days` for windowed reports |
| GET | `/api/reports/{id}/export` | `inventory:read` + `export:data` | `format=csv\|xlsx`; attachment with metadata header |
| GET | `/api/admin/schema` | `admin:tenant` | mapping vs source: drift, unmapped columns, health |
| GET | `/api/admin/capabilities` | `admin:tenant` | capability matrix with missing fields |
| GET | `/api/admin/audit` | `audit:read` | tenant's audit events; filters `decision`, `action` prefix |
| POST | `/api/admin/reconciliation` | `admin:tenant` + `cost:read` | `{tolerance, rows[{warehouse_id,currency,value}]}` → per-line status + `passed` |
| GET | `/api/agent/suggestions` | `chat:use` | starter questions |
| POST | `/api/agent/chat` | `chat:use` | `{message}` (2–500 chars) → `{mode, notice, kind (tools/clarify/unsupported), answer, blocks[], tool_calls[], provenance[], warnings[], follow_ups[], choices[], grounding}` |
| POST | `/api/agent/feedback` | `chat:use` | `{rating: up/down, reason?}` recorded in the audit trail |
| POST | `/api/query` | `query:run` | body = QueryPlan → envelope |

Exact request/response models: FastAPI OpenAPI at `/api/docs` (enabled only when `APP_ENV != production`).
