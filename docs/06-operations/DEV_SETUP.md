# Development Setup

Verified on Windows 11 (2026-10-27). Commands are identical on macOS/Linux unless noted.

## Prerequisites

| Tool | Version used | Notes |
|---|---|---|
| uv | 0.11.15 | Installs/uses CPython 3.13 automatically. Never call bare `python`. |
| Node.js | 22.20 | |
| pnpm | 11.10 | pnpm 11 enforces a minimum package release age; don't add exclusions to bypass it. |
| git | any recent | |

No Docker or database server is needed: synthetic warehouses are DuckDB files, the app metadata DB is SQLite.

## First run

```bash
# API
cd services/api
uv sync                                   # creates .venv from uv.lock
uv run lumiant-synthetic generate --all   # writes data/synthetic/demo-alpha.duckdb and demo-beta.duckdb (~6 s)
uv run uvicorn --factory lumiant.main:create_app --port 8000
```

```bash
# Web (second terminal)
cd apps/web
pnpm install
pnpm dev            # http://localhost:3000
```

Or from the repo root: `pnpm run data`, `pnpm run dev:api`, `pnpm run dev:web`.
In the Claude desktop app, `.claude/launch.json` defines `api` and `web` preview servers.

## How the pieces connect

- Browser → `http://localhost:3000` (Next.js). Requests to `/api/*` are proxied by Next.js to `LUMIANT_API_ORIGIN` (default `http://127.0.0.1:8000`), so the session cookie is same-origin.
- The API reads tenant configs from `services/api/config/tenants/*.yaml` and the synthetic DuckDB files they point to, **read-only**.
- The API creates `services/api/var/app.db` (SQLite) on first start and runs migrations automatically in development.

## Configuration (environment variables)

API (`services/api/.env`, see `.env.example`; prefix `LUMIANT_`):

| Variable | Default | Meaning |
|---|---|---|
| `LUMIANT_APP_ENV` | `development` | `development` / `test` / `production` |
| `LUMIANT_AUTH_MODE` | `dev` | `dev` is refused when `APP_ENV=production`; `oidc` is not implemented yet (the API refuses to start) |
| `LUMIANT_DEV_JWT_SECRET` | random per process | ≥ 32 chars if set; sessions reset on restart when unset |
| `LUMIANT_SESSION_TTL_MINUTES` | 480 | |
| `LUMIANT_COOKIE_SECURE` | `false` | must be `true` in production |
| `LUMIANT_DATA_DIR` | `services/api` | base for tenant connection paths |
| `LUMIANT_APP_DB_URL` | `sqlite:///…/services/api/var/app.db` | PostgreSQL in production (untested locally) |
| `LUMIANT_AUTO_MIGRATE` | `true` | |
| `LUMIANT_LOG_LEVEL` | `INFO` | JSON logs to stdout |
| `LUMIANT_AGENT_PROVIDER` | `rules` | `rules` (built-in, no data leaves) or `anthropic` (needs `LUMIANT_ANTHROPIC_API_KEY`, `LUMIANT_AGENT_MODEL`, **and** `ai.external_provider_approved: true` in the tenant YAML) |

Web: `LUMIANT_API_ORIGIN` (default `http://127.0.0.1:8000`; read at build time for `next build`).

## Demo users (development authentication only)

| User | Sees |
|---|---|
| `alpha.admin` | Demo Alpha, all 6 warehouses, values, generated SQL in provenance |
| `alpha.north_manager` | Demo Alpha, NORTH department (1100, 1110, 1120), values |
| `alpha.analyst` | Demo Alpha, warehouse 3100 only, **no values/costs** |
| `beta.admin` | Demo Beta, all warehouses, EUR **and** GBP (never added together) |
| `beta.user` | Demo Beta, Leeds (LDS1, GBP) only |

## Common tasks

| Task | Command |
|---|---|
| Regenerate synthetic data | stop the API first (DuckDB file lock), then `uv run lumiant-synthetic generate --all` |
| One tenant / custom size | `uv run lumiant-synthetic generate --tenant demo-beta --items 100 --months 12 --seed 7` |
| API docs (dev only) | http://localhost:8000/api/docs |
| Reset the app DB | stop the API, delete `services/api/var/app.db*` |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `… is in use — stop the API before regenerating synthetic data` | DuckDB file locked by the running API |
| Login page says the API is unreachable | API not running on 8000, or `LUMIANT_API_ORIGIN` wrong |
| `Development authentication cannot be enabled when LUMIANT_APP_ENV=production` | Intended guard (ADR-0004) |
| `LUMIANT_AUTH_MODE=oidc is not implemented yet` | Intended: OIDC arrives in M6 |
| pnpm `ERR_PNPM_MINIMUM_RELEASE_AGE_VIOLATION` | A dependency version is too new; pin an older one rather than excluding it |
| Pages look faded in a background tab | Entrance animations pause while the tab is hidden (ISSUES #10) |
