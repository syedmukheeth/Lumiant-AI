# Deployment

Status: **Prepared, never executed.** No environment has been deployed to. Nothing here may be applied to a customer
environment without written approval. Container files and CI are unverified (`PRODUCTION_READINESS.md`).

## Topology (target)

```
users ─ TLS ─► customer ingress / gateway (SSO, OIDC bearer token)
                 ├─► web   (Next.js, port 3000)  ── /api/* ──►  api (FastAPI, port 8000)
                 └─────────────────────────────────────────►  api
api ─► PostgreSQL (app metadata + audit)        api ─► customer warehouse (read-only account)
api ─► approved LLM endpoint (optional, only if the tenant approves external AI)
```
Public hosting is not assumed: everything runs in the customer's private network or cloud tenant.

## Requirements

| Need | Detail |
|---|---|
| Compute | api: 2 vCPU / 2 GB to start; web: 1 vCPU / 1 GB. Scale api with query concurrency. |
| App database | PostgreSQL 15+, encrypted at rest, backed up. Driver installed with the `postgres` extra. |
| Warehouse access | network path + **read-only** account on approved views (`02-architecture/CONNECTORS.md`). Only DuckDB is a tested connector today; others need new connector code and tests. |
| Identity | OIDC provider; a gateway forwards `Authorization: Bearer <token>`. Tenant YAML `oidc:` block maps issuer/audience/groups. |
| Secrets | injected as environment/secret-manager values; never in images or git. |
| TLS / HSTS | terminated at the ingress. |
| Egress | warehouse; LLM endpoint only if approved. |

## Configuration (production)

| Variable | Value |
|---|---|
| `LUMIANT_APP_ENV` | `production` (disables API docs; refuses dev auth and insecure cookies) |
| `LUMIANT_AUTH_MODE` | `oidc` |
| `LUMIANT_COOKIE_SECURE` | `true` |
| `LUMIANT_APP_DB_URL` | `postgresql+psycopg://…` from the secret manager |
| `LUMIANT_AUTO_MIGRATE` | `false` in production; run `alembic upgrade head` as a release step |
| `LUMIANT_TENANT_CONFIG_DIR` | mounted directory of tenant YAML (mappings, roles, `oidc`, `ai`) |
| `LUMIANT_RATE_LIMIT_*_PER_MIN` | tune per tenant size |
| `FORWARDED_ALLOW_IPS` | the proxy's address, so rate limiting sees client addresses |
| `LUMIANT_AGENT_PROVIDER` | `rules` unless the customer has approved an external provider |

## Release procedure (draft)
1. CI green (`.github/workflows/ci.yml`); audits clean.
2. Build images; scan them; tag with the git commit.
3. Back up the app database.
4. Run migrations: `alembic upgrade head` (one-off job).
5. Deploy api, check `/api/health/ready`, then web.
6. Smoke test: sign in through the gateway, overview loads, one report exports, audit shows the requests.
7. Watch error rates and the audit log for denials.

## Rollback
Redeploy the previous image tag. Migrations are additive; if one must be reverted, restore the pre-release backup rather than
downgrading data. See `RUNBOOK.md`.
