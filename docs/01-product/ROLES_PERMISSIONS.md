# Roles & Permissions

The brief's roles are **not final** (F-008). Roles are defined per tenant in YAML; this file documents the model and the synthetic demo configuration. Customer roles are blocked on Q-010/Q-011.

## Model

```
Principal = user_id + tenant_id + roles[] → permissions[]  +  data scope
data scope = allowed warehouses  (derived from departments and/or explicit warehouse list; "*" = all in tenant)
```

Enforcement points (all server-side):
1. **Route** — each endpoint declares a required permission.
2. **Metric / analysis** — each declares required permissions (e.g. value metrics need `cost:read`).
3. **Validator** — dataset allowlist, sensitive-field check, scope filter injection, explicit out-of-scope filter → 403.
4. **Connector** — per-tenant engine; DuckDB opened read-only (customer DBs: read-only service account).

## Permissions (M1)

| Permission | Grants |
|---|---|
| `dashboard:read` | Overview metrics endpoints |
| `inventory:read` | Inventory explorer, filters, below-reorder (quantities) |
| `cost:read` | Any field with `sensitivity=cost` (valuation price, unit cost, stock value) and value metrics |
| `query:run` | `POST /api/query` with a QueryPlan |
| `query:view_sql` | See compiled SQL in provenance |
| `audit:read` | Audit events (M5 UI) |
| `admin:tenant` | Tenant administration (M5) |

Planned later: `export:csv`, `export:xlsx`, `report:create`, `chat:use`, `mapping:edit`, `users:manage`.

## Demo roles (synthetic tenants)

| Role | Permissions | Scope |
|---|---|---|
| `super_admin` | all M1 permissions | all warehouses |
| `dept_admin` | dashboard, inventory, cost, query:run | warehouses of assigned departments |
| `standard_user` | dashboard, inventory, cost, query:run | assigned warehouses |
| `viewer_no_cost` | dashboard, inventory | assigned warehouses; **no cost fields** |

## Demo users (development auth only — never valid in production)

| Username | Tenant | Role | Scope |
|---|---|---|---|
| `alpha.admin` | demo-alpha | super_admin | all |
| `alpha.north_manager` | demo-alpha | dept_admin | department `NORTH` |
| `alpha.analyst` | demo-alpha | viewer_no_cost | one warehouse |
| `beta.admin` | demo-beta | super_admin | all |
| `beta.user` | demo-beta | standard_user | one warehouse |

Exact definitions live in `services/api/config/tenants/*.yaml`; if they differ from this table, the YAML is authoritative and this file must be corrected.
