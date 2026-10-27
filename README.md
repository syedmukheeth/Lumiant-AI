# Lumiant Inventory Intelligence Platform

AI-ready inventory intelligence for Lumiant Group's customers: read-only connection to a customer's data warehouse → canonical inventory model → secured, deterministic query engine → dashboard (and, from milestone M3, a chat agent).

> **Status: Milestone 1 (foundation) — runs on synthetic data only.** No customer system has been connected. See [`docs/00-context/CURRENT_STATE.md`](docs/00-context/CURRENT_STATE.md) for exactly what is verified, simulated and pending.

## What works today

- Two **synthetic** demo tenants with different physical schemas (SAP-style names vs snake_case, USD vs EUR+GBP), generated deterministically into DuckDB files.
- A **canonical inventory model** and per-tenant **mapping** (YAML), validated at startup.
- A **query engine** every screen goes through: structured plan → validation (dataset/field allowlist, cost-field permission, warehouse scope injected by the server, currency/UoM safety rails) → parameterized SQL → SQL safety guard → read-only execution → provenance → audit log.
- **Development-only sign-in** with role- and warehouse-scoped users (refuses to start in production mode).
- **Web app**: overview (inventory value per currency, items, stock lines, below-reorder, value by warehouse / item group / ABC / stage) and an inventory explorer (search, filters, sort, paging), each number with a "Source" slip showing where it came from.

## Quick start (Windows, macOS, Linux)

Prerequisites: [uv](https://docs.astral.sh/uv/) (Python 3.13 is installed by uv), Node 22+, pnpm 11.

```bash
cd services/api
uv sync
uv run lumiant-synthetic generate --all
uv run uvicorn --factory lumiant.main:create_app --port 8000
```

In a second terminal:

```bash
cd apps/web
pnpm install
pnpm dev
```

Open http://localhost:3000 and pick a demo user. Details, troubleshooting and the full command list: [`docs/06-operations/DEV_SETUP.md`](docs/06-operations/DEV_SETUP.md). Tests: [`docs/06-operations/TESTING.md`](docs/06-operations/TESTING.md).

## Repository layout

| Path | What |
|---|---|
| `services/api/` | FastAPI service (Python 3.13, uv): query engine, auth, synthetic data, tests |
| `apps/web/` | Next.js 16 web app (TypeScript, Tailwind 4, React Query, Recharts), unit + e2e tests |
| `docs/` | The project knowledge base — context, requirements, architecture, ADRs, security, domain rules, plan, logs |
| `CLAUDE.md`, `AGENTS.md` | Entry points for AI coding assistants (rules + logging protocol) |

## Documentation

Start at [`docs/README.md`](docs/README.md). Every session's work is logged in [`docs/logs/WORKLOG.md`](docs/logs/WORKLOG.md).
