# Test Runs

Every test, lint, type-check or audit run is recorded here: date, step, exact command, result. Failures are recorded too — never deleted.

| Date | Step | Command | Result | Notes |
|---|---|---|---|---|
| 2026-10-27 | M1-2 | spike run 1 (`uv run --no-project … python spike.py`) | FAIL | `ILIKE ESCAPE '\\'` rejected by DuckDB |
| 2026-10-27 | M1-2 | spike run 2 | FAIL | interrupt test hit an aborted transaction from the write test (script bug: missing rollback) |
| 2026-10-27 | M1-2 | spike run 3 | FAIL | script syntax error (edit artifact) |
| 2026-10-27 | M1-2 | spike run 4 | **PASS** | all checks in ADR-0005 |
| 2026-10-27 | M1-3 | `uv run pytest -q` | **27 passed** | config, tenancy, mapping unit tests |
| 2026-10-27 | M1-3 | `uv run ruff check .` | 11 errors → fixed | style/PT018/E501/E741 |
| 2026-10-27 | M1-3 | `uv run mypy` (strict) | 7 errors → fixed → **clean** | SA type map typing |
| 2026-10-27 | M1-3 | `uv run pytest -q` (after fixes) | **27 passed** | |
| 2026-10-27 | M1-4 | `uv run lumiant-synthetic generate --all` | **OK** | alpha 3.8 s, beta 2.1 s |
| 2026-10-27 | M1-4 | `uv run pytest -q` | **43 passed** | +16 synthetic tests (determinism, Σ movements = balances for both schemas, no negative running balances, referential integrity, join-key uniqueness, scenarios, DECIMAL types) |
| 2026-10-27 | M1-4 | `uv run ruff check .` / `uv run mypy` | 20 + 3 findings → fixed → **clean** | |
| 2026-10-27 | M1-5 | `uv run pytest -q -x` | 1 failed | DuckDB same-file config conflict between test raw connection and connector |
| 2026-10-27 | M1-5 | `uv run pytest -q` | 98 passed, **6 failed** | Decimal rounding by SQLAlchemy (real bug), guard parse with pyformat dialect in test, guard reason ordering, test plan shape |
| 2026-10-27 | M1-5 | `uv run pytest -q` | **104 passed** | after fixes |
| 2026-10-27 | M1-5 | `uv run ruff check .` / `uv run mypy` | 13 + 9 findings → fixed → **clean** | |
| 2026-10-27 | M1-6 | `uv run pytest -q` | 127 passed, **6 failed** | SQL guard rejected `AND`/`OR` (sqlglot `Func` subclasses) in metrics gap plan, search and below-reorder |
| 2026-10-27 | M1-6 | `uv run pytest -q` | **133 passed** (2 warnings) | after guard allowlist fix; warnings = Starlette httpx deprecation + 1 related |
| 2026-10-27 | M1-6 | `uv run ruff check .` / `uv run mypy` | 4 findings → fixed → **clean** | |
| 2026-10-27 | M1-7 | `uv run pytest -q tests/unit/test_audit_store.py` | **1 passed** | regression for first-run SQLite dir bug |
| 2026-10-27 | M1-7 | `pnpm typecheck` / `pnpm lint` | **clean** | |
| 2026-10-27 | M1-7 | `pnpm test` (vitest) | 14 passed, **6 failed** → **20 passed** | failures were test env (NBSP in Intl output, missing ResizeObserver in jsdom) |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | 2 passed, **3 failed** | click before router settled; hidden previous route matched locator |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | 3 passed, **2 failed** | duplicate pager locator; options not loaded yet |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | 4 passed, **1 failed** | **real bug**: debounced search overwrote warehouse filter |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | **5 passed** | after fix; includes `next build` |
| 2026-10-27 | M1-8 | `pnpm run check` (root: ruff, ruff format, mypy, pytest, eslint, tsc, vitest) | **all green**: 134 API passed, 20 web passed | 2 warnings (Starlette httpx deprecation; a test-only Pydantic enum warning, then fixed) |
| 2026-10-27 | M1-8 | `uv run pytest -q` after warning fix | **134 passed**, 1 warning | |
| 2026-10-27 | M1-8 | `pnpm audit` (apps/web) | **0 known vulnerabilities** | |
| 2026-10-27 | M1-8 | `uvx pip-audit -r <exported requirements>` | **0 known vulnerabilities** | first attempt not run: a safety check blocked a temp-file path outside the project; rerun with the scratchpad |
| 2026-10-27 | M2 | `uv run pytest -q` | **177 passed** | +26 costing/ABC hand-computed, +5 item-code, +10 analysis integration tests vs raw SQL |
| 2026-10-27 | M2 | `uv run ruff check .` / `mypy` | clean (E501 exempted in `analyses/risks.py`) | |
| 2026-10-27 | M2 | `pnpm exec playwright test` | **8 passed** | +3: risks, costs, role-hidden nav |
| 2026-10-27 | M3 | `uv run pytest -q` | 219 passed, **1 failed** | model prose overwrote a failed-tool message (real bug) |
| 2026-10-27 | M3 | `uv run pytest -q` | **220 passed** | golden (14), adversarial (8), grounding (4), provider/endpoint tests with a fake Anthropic client |
| 2026-10-27 | M3 | `pnpm exec playwright test` | 9 passed, **1 failed** | ambiguous "Ask" button locator (test bug) → exact match → **11 passed** |
| 2026-10-27 | M4 | `uv run pytest -q` | **234 passed** | +14 report/export tests |
| 2026-10-27 | M4 | `pnpm exec playwright test` | **12 passed** | +2 (guided menu + reports; reduced role) |
| 2026-10-27 | M5 | `uv run pytest -q` | **244 passed** | +10 admin tests |
| 2026-10-27 | M5 | `pnpm exec playwright test` | **14 passed** | +2 admin (workflow, role hiding) |
| 2026-10-27 | M6 | `uv run pytest -q` | 250 passed → 266 passed after OIDC | rate limiting, then OIDC; 1 test-side failure fixed (hand-built forged HS256 token) |
| 2026-10-27 | M6 | `pnpm exec playwright test` | **15 passed** | production build with strict CSP; no CSP violations on any page |
| 2026-10-27 | M6 | `uvx pip-audit` / `pnpm audit` | **0 known vulnerabilities** | after adding anthropic, openpyxl, pyjwt[crypto], psycopg extra |
| 2026-10-27 | CV-1 | Linux (cloud sandbox, Python 3.13.17, Node 22.22, uv 0.11.32, pnpm 11.10.0): `uv sync --frozen && ruff check . && ruff format --check . && mypy && pytest -q` | **clean · 95 files formatted · mypy 70 files OK · 266 passed** | no Linux-only problems (paths, line endings, case) found |
| 2026-10-27 | CV-1 | `pnpm install --frozen-lockfile && pnpm lint && pnpm typecheck && pnpm test` | **clean · 20 passed** | |
| 2026-10-27 | CV-1 | `pnpm exec playwright install --with-deps chromium` | **FAILED**: `cdn.playwright.dev` blocked (403) by the sandbox network policy | environment limit, not a repo defect (ISSUES #21) |
| 2026-10-27 | CV-1 | `pnpm e2e` | **15 failed** (browser build 1248 missing) | |
| 2026-10-27 | CV-1 | `playwright test -c playwright.local.config.ts` (uncommitted config pointing at preinstalled Chromium 1243) | **15 passed** (53 s) | production build + isolated API |
| 2026-10-27 | CV-2 | `docker info` | daemon not running → started `dockerd` manually → `hello-world` ran | |
| 2026-10-27 | CV-2 | `docker build services/api` | **FAILED**: `ghcr.io/astral-sh/uv` blob blocked (403); Docker Hub `429 Too Many Requests` | environment limit |
| 2026-10-27 | CV-2 | Workaround for the sandbox only: `python:3.13-slim` / `node:22-alpine` pulled from `mirror.gcr.io` and re-tagged with the sandbox TLS CA added; a local stand-in `ghcr.io/astral-sh/uv:0.11` holding the host's uv 0.11.32 binary | | Dockerfiles themselves unmodified for these steps. **Not the real upstream images** |
| 2026-10-27 | CV-2 | `docker build services/api` (first try after CA fix) | **built** | |
| 2026-10-27 | CV-2 | `docker build apps/web` | **built** (Next production build inside the image) | |
| 2026-10-27 | CV-2 | `docker compose up --build -d` | **FAILED**: api crashed `PermissionError: /app/data` — **real bug**: non-root user cannot write | fixed: `/data` owned by `lumiant`, `LUMIANT_DATA_DIR=/data` |
| 2026-10-27 | CV-2 | `docker compose up --build -d --wait` after fix | api **healthy** (uid 10001), web up | |
| 2026-10-27 | CV-2 | Browser against http://127.0.0.1:3000: sign in as `alpha.admin` → overview | **OK**: items 585, value `USD 2,767,451.83`, SYNTHETIC badge, **0 CSP violations** | also curl smoke: `/login`, `/api/health`, dev-login, `/api/auth/me` |
| 2026-10-27 | CV-2 | `docker run lumiant-ai-api` (production defaults) | refuses to start: OIDC mode needs a tenant `oidc` block | expected; `psycopg` 3.3.6 and `redis` 7.4.1 import OK in the image |
| 2026-10-27 | CV-3 | `uvx --from actionlint-py actionlint .github/workflows/ci.yml` (1.7.12) | **clean** (and a deliberately bad file is rejected) | first-pass review found `pnpm/action-setup` `version:` + `packageManager` conflict → removed |
| 2026-10-27 | CV-3 | After adding postgres/redis/docker jobs: actionlint | **clean**; the new jobs' commands were run locally (alembic up/down/up, pytest with env, compose smoke) | the workflow has **not** run on GitHub Actions |
| 2026-10-27 | CV-4 | PostgreSQL 16.x (apt) + `alembic upgrade head`, `downgrade base`, `upgrade head` | **OK**, `alembic_version` = `0001`; table/index DDL as expected | one false start: role lacked rights on the `postgres` DB's `public` schema (PG ≥15 default) — local setup only |
| 2026-10-27 | CV-4 | `LUMIANT_TEST_PG_ADMIN_URL=… uv run pytest -q` (every API test app gets a fresh PostgreSQL database) | **266 passed**; with new PostgreSQL test **267 passed** | no PostgreSQL-specific defect found |
| 2026-10-27 | CV-5 | `pytest tests/unit/test_ratelimit_redis.py tests/integration/test_hardening.py` against Redis 7.0.15 | **14 passed** (shared window across instances, slide/recover, TTL, 2-replica API 401×4→429, outage fallback) | |
| 2026-10-27 | CV-5 | `uv run pytest -q` with PG + Redis env | **275 passed** | |
| 2026-10-27 | CV-5 | `uv run pytest -q` default (SQLite, no Redis) | **269 passed, 6 skipped** (4 Redis + 1 Redis API + 1 PG, need env) | |
| 2026-10-27 | CV-5 | `ruff check` / `ruff format --check` / `mypy` | 5 lint findings (SIM105, S110, PT018×3) in new code → fixed → **clean** | |
| 2026-10-27 | CV-5 | Nonce CSP: first build | **static shell had inline scripts without a nonce** (PPR) → `cacheComponents` off + `connection()` in root layout | ADR-0007 |
| 2026-10-27 | CV-5 | `pnpm lint` | 1 error (`no-sync-scripts` on a raw `<script src>`) + 1 warning → `next/script`, optional catch binding → **clean** | |
| 2026-10-27 | CV-5 | `pnpm test` / `pnpm typecheck` | **23 passed** (+3 `buildCsp`) · clean | |
| 2026-10-27 | CV-5 | `playwright test -c playwright.local.config.ts` | **16 passed** (CSP test strengthened: no `unsafe-inline` in script-src, every inline script carries the response nonce, nonce differs per request; +1 saved-theme test) | |
| 2026-10-27 | CV-6 | `pnpm audit` · `uvx pip-audit` on `uv export --extra postgres --extra redis` | **0 known vulnerabilities** both | |
