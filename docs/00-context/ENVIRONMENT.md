# Environment

## Development machine (verified 2026-10-26, session 01)

| Item | Value | How verified |
|---|---|---|
| OS | Windows 11 Home Single Language 10.0.26300 | session environment |
| Shells | PowerShell 5.1 (primary), Git Bash | session environment |
| Node.js | v22.20.0 | `node --version` |
| npm | 11.8.0 | `npm --version` |
| pnpm | 11.10.0 | `pnpm --version` |
| Python | **no system `python`** (Store alias only). CPython 3.13.13 and 3.12.13 managed by uv | `uv python list --only-installed` |
| uv | 0.11.15 | `uv --version` |
| git | 2.50.1.windows.1 | `git --version` |
| Java | 24.0.1 | `java -version` |
| Docker / WSL | **not installed** | `docker --version`, `wsl --status` |
| PostgreSQL / SQL Server / Oracle clients | **not installed** | `psql`, `sqlcmd` not found |
| yarn / bun / go / gh | not installed | — |
| CPU / RAM / free disk (E:) | 8 logical CPUs / 7.8 GB / ~235 GB | `Get-CimInstance` |

**Consequences**
- Always run Python through `uv run …` (never bare `python`).
- No local PostgreSQL/SQL Server/Oracle → those connectors cannot be integration-tested on this machine. The synthetic customer warehouse uses **DuckDB** files (ADR-0003). The app metadata DB uses **SQLite** in development (PostgreSQL targeted for production, untested locally).
- Path contains a space (`E:\LUMIANT AI`) → always quote paths in scripts.

## Package versions (checked against npm/PyPI registries 2026-10-26)

### Frontend (`apps/web`)
| Package | Latest seen | Pinned / used | Reason |
|---|---|---|---|
| next | 16.4.3 | 16.4.x | current stable |
| react / react-dom | 19.3.1 | 19.3.x | Next 16 peer |
| typescript | 7.0.2 (`latest`), 6.0.3, 5.9.3 | **5.9.3** | TS 7 is the Go-native port; Next build type-check compatibility unverified (ADR-0005) |
| tailwindcss / @tailwindcss/postcss | 4.3.3 | 4.3.x | v4 CSS-first config |
| recharts | 3.10.1 | 3.10.x | React-native charts, accessible enough, small API |
| @tanstack/react-query | 5.105.0 | 5.x | server-state caching |
| @tanstack/react-table | 9.3.1 | **not used** | v9 is new major; simple custom table suffices for M1 |
| zod | 4.6.7 | 4.x | response validation |
| radix-ui | 1.8.1 | 1.x | accessible primitives |
| lucide-react | 1.61.0 | 1.x | icons |
| vitest | 5.0.5 | 5.x | unit tests |
| @playwright/test | 1.64.1 | 1.64.x | e2e |
| eslint / eslint-config-next | 10.13.0 / 16.4.3 | matching Next | lint |

### Backend (`services/api`)
| Package | Latest seen | Pinned / used | Reason |
|---|---|---|---|
| fastapi | 0.162.0 | 0.162.x | API framework |
| uvicorn | 0.54.0 | 0.54.x | ASGI server |
| pydantic / pydantic-settings | 2.14.1 / 2.16.1 | 2.x | models, env validation |
| sqlalchemy | 2.1.6 (2.1.0 released 2026-09-24), 2.0.55 | **2.0.x** (decided after spike — see ADR-0005) | `duckdb-engine` 0.17 predates SA 2.1 |
| duckdb | 2.0.0 (released 2026-10-21), 1.5.6 | **1.5.x** | 2.0.0 is 5 days old (ADR-0005) |
| duckdb-engine | 0.17.0 (last release 2025-03) | 0.17.0 (if spike passes) | SQLAlchemy dialect for DuckDB |
| sqlglot | 30.25.0 | 30.x | SQL AST guard |
| alembic | 1.20.1 | 1.20.x | migrations for app DB |
| PyJWT | 2.15.1 | 2.x | dev session tokens |
| pyyaml | 6.0.3 | 6.x | tenant config |
| pytest / pytest-cov | 9.1.1 / 7.1.0 | 9.x | tests |
| httpx | 0.28.1 | 0.28.x | FastAPI TestClient |
| ruff | 0.17.2 | 0.17.x | lint/format |
| mypy | 2.4.0 | 2.x | type check |

Exact resolved versions are in `services/api/uv.lock` and `apps/web/pnpm-lock.yaml` once created; this table is updated if pins change.

## Resolved versions in use (end of M1, 2026-10-27)

Authoritative sources: `services/api/uv.lock`, `apps/web/pnpm-lock.yaml`. Differences from the table above are deliberate:

| Package | Resolved | Why it differs |
|---|---|---|
| react / react-dom | 19.3.0 | pinned by `create-next-app@16.4.3` |
| @tanstack/react-query | **5.104.5** | 5.105.0 was published one day earlier and failed pnpm 11's minimum-release-age policy; the policy was kept, not bypassed |
| eslint | 9.39.5 | `eslint-config-next@16.4.3` template uses ESLint 9 |
| @types/node | 22.20.5 | Vitest 5 requires Node types ≥ 22 |
| Tailwind integration | `@tailwindcss/turbopack` 4.3.3 | Next 16.4 template uses the Turbopack loader instead of PostCSS |
| starlette | 1.10.0 | via FastAPI 0.162 |
| Python packages | fastapi 0.162.0, uvicorn 0.54.0, pydantic 2.14.1, pydantic-settings 2.16.1, sqlalchemy 2.0.55, duckdb 1.5.6, duckdb-engine 0.17.0, sqlglot 30.25.0, alembic 1.20.1, pyjwt 2.15.1, pyyaml 6.0.3, pytest 9.1.1, ruff 0.17.3, mypy 2.4.0 | as pinned |
| Playwright browser | Chromium (installed with `pnpm exec playwright install chromium`) | e2e only |

Dependency audits on 2026-10-27: `pnpm audit` → no known vulnerabilities; `pip-audit` on the exported API requirements → no known vulnerabilities.
