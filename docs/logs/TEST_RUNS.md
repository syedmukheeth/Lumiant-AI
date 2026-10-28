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
| 2026-10-27 | S02-1 | GitHub Actions run #2 (`f437fdf`), job `api` | **FAILED** at `uv run mypy` (16 s); ruff + format passed; `e2e` skipped | logs need sign-in; step status read from the public run page |
| 2026-10-27 | S02-1 | Windows: `uv sync --frozen` (no extras) → `uv run mypy` | **reproduced**: `ratelimit.py:97: Cannot find implementation or library stub for module named "redis" [import-not-found]` | |
| 2026-10-27 | S02-1 | After the mypy override, no extras: `ruff check .` · `ruff format --check .` · `mypy` · `pytest -q` | **clean · 96 files formatted · 70 files OK · 269 passed, 6 skipped** | |
| 2026-10-27 | S02-1 | Same with `uv sync --frozen --extra redis --extra postgres` (redis 7.4.1, psycopg 3.3.6): `mypy` · `pytest -q` | **70 files OK · 269 passed, 6 skipped** | skips need live PostgreSQL/Redis env vars |
| 2026-10-27 | S02-2 | GitHub Actions run on `3ef74b9` (run id 40504453322) | **success**: `api`, `api-postgres-redis`, `web`, `docker`, `e2e` all green | first GitHub run of `e2e` (incl. `playwright install --with-deps chromium`) and of the Docker build against real upstream images; job status read from the public GitHub API |
| 2026-10-27 | S03-1 | Read-only structure profile of the two client XLSX files (scratch script outside the repo, prints header, cell types and masked patterns only) | header contract confirmed; codes arrive as text; quantities/values as Excel numbers; stock list ends with a block of SAP total rows (blank Plant/Material/Material type, one per unit of measure, first one also carries the value totals); per-unit quantity totals equal the detail sums | no values copied anywhere |
| 2026-10-27 | S03-2 | `uv run ruff check .` · `ruff format --check .` · `mypy` after Part B code | 3 lint findings (B023 closure over loop variable, 2× E501) + mypy `no-untyped-call` (lambda) → fixed → **clean**, 74 files OK | |
| 2026-10-27 | S03-3 | `uv run pytest -q` (first run with demo-gamma) | **2 expected failures**: `/api/health/ready` now counts 3 sources, `test_demo_tenants_load` lists 3 tenants → assertions updated to the new tenant set (still exact) | not weakened: equality kept |
| 2026-10-27 | S03-4 | Smoke via TestClient as `gamma.admin` (scratch script) | **found**: SQL guard refused value-map CASE (`function_not_allowed:IF`, sqlglot models WHEN as `If`) → `exp.Case`/`exp.If` allowed; `value_by_warehouse` report and metric failed on unmapped `warehouse.name` → optional descriptive dimensions | |
| 2026-10-27 | S03-5 | `uv run pytest -q` | **342 passed, 6 skipped** (env-gated PG/Redis) | +73 tests |
| 2026-10-27 | S03-6 | **Real client import** `uv run lumiant-ingest sap … --tenant client-sap --as-of 2026-10-27` (owner-authorized, local only) | exit 0, **control-total gate passed**, 215 s; output = counts only, kept in the session scratchpad | reconciliation with a plain 0.01 tolerance reported many differing lines |
| 2026-10-27 | S03-7 | Analysis of the differing lines (counts by bucket only) | all differences are within \|quantity\| × 0.005 ÷ price unit, i.e. explained by SAP showing the moving-average price rounded to 2 decimals → rule made rounding-aware (`price_rounding`) | none beyond the bound |
| 2026-10-27 | S03-8 | `uv run pytest -q` after the rounding rule | **343 passed, 6 skipped** (138 s) | |
| 2026-10-27 | S03-9 | Real import re-run with the new view | exit 0, gate passed (55 s, files cached), **0 lines beyond the rounding bound**; `git status --ignored` → `services/api/var/` ignored, **no private file listed** | |
| 2026-10-27 | S03-10 | API smoke on the real extract (`app_env=development`, private dir, flag; scratch script printing status codes and column names only) | sign-in 200; meta `customer_extract`, `synthetic=false`; explorer, filters, data quality (all checks ran), value metrics, capabilities, schema check, reports → 200; value by ABC (assigned) → 400 `field_not_available` (expected: ABC is per plant, ISSUES #28) | |
| 2026-10-27 | S03-11 | `pnpm install --frozen-lockfile` (new worktree) · `pnpm lint` · `pnpm typecheck` | installed (17.7 min, slow disk) · **clean** · **clean** | |
| 2026-10-27 | S03-12 | `pnpm test` | first run **failed to start** ("no tests, 4 errors" while the real import was using the CPU); rerun **23 passed** | environment timing, no code change |
| 2026-10-27 | S03-13 | Playwright via an uncommitted copy of `playwright.config.ts` on ports 8200/3200 (8100/3100 were held by another local process) | **16 passed** (5.3 min); one transient `ECONNRESET` logged by the web proxy during the risks test (test passed) | temporary config deleted afterwards |
| 2026-10-27 | S03-14 | Leak scan: every distinct real material number, material group, description (≥ 12 chars), non-standard material/MRP type and non-numeric plant vs all tracked + untracked repo files (counts only) | **no real values in files written this session**; only trivial collisions (single-digit numbers, a 5-digit number equal to the container uid, one token inside the unchanged `uv.lock`) | |
| 2026-10-27 | S03-15 | Built-in assistant on demo-gamma (5 questions) | dormant / below-reorder / expiring answer "not mapped"; value-by-warehouse answer fails on `warehouse.name` (ISSUES #29) | Part C |
| 2026-10-27 | D1-1 | `contrast.mjs --color fg:bg` for every text token on bg/surface/surface-2/surface-3, both themes, plus accent-ink/accent, inverse chips, -soft fills, control-line | **all text pairs ≥ 4.5:1** (worst: dark ink-3/surface-3 4.93, light signal/surface-2 4.89, light accent/surface-2 4.91); control-line 3.01–3.65 (≥ 3:1); first light control-line candidate #8893a1 failed on surface-2 (2.70) → #7c8795 | line/line-strong are decorative, not checked as text |
| 2026-10-27 | D1-2 | `validate_palette.js` dataviz reference palette `--mode light --surface #ffffff` and `--mode dark --surface #0f1318` | **PASS both** (adjacent CVD worst ΔE 9.1 / 8.4, normal-vision 19.6 / 19.3); light WARN: aqua 2.82, yellow 2.17, magenta 2.69 < 3:1 → relief rule (labels/table) documented | FRONTEND.md § Design tokens |
| 2026-10-27 | D1-3 | `pnpm add --save-exact motion@14.1.0 cmdk@1.1.1 geist@1.7.2` (≥ 2 weeks old; motion 14.7.1 / geist 1.8.2 newer but too fresh, DEC-013) | OK | first `pnpm install` in the worktree took 7m47s |
| 2026-10-27 | D1-4 | `token-lint.mjs src` | **No hardcoded color literals in 41 files** |  |
| 2026-10-27 | D2-1 | `pnpm typecheck` · `pnpm lint` | **clean · clean** |  |
| 2026-10-27 | D2-2 | `pnpm test` (first run) | **1 suite failed to load**: `TypeError: The URL must be of scheme file` (`new URL(…, import.meta.url)` under jsdom) → read via `process.cwd()` | test bug, not product |
| 2026-10-27 | D2-2 | `pnpm test` | **41 passed** (6 files; +18: palette ×8, shortcuts ×4, theme/rail ×2, theme-init.js ×4) |  |
| 2026-10-27 | D2-3 | Browser (dev, 1440 + 1024 px): sign-in, overview, ⌘K materials → explorer, Ask → assistant, in-page Ask, G O, collapse rail, light theme | works; **found and fixed**: pending dot always visible (`animate-pulse` overrides opacity), header wrapping at 1024 px, chart category labels clipped/wrapped with Geist (custom one-line tick), palette showed "No matching" beside results, cmdk fuzzy filter matched "valve" → Inventory (word-prefix filter + test) | `[` key via the pane's key tool did not reach the page; verified by dispatching the event and by e2e |
| 2026-10-27 | D2-4 | `pnpm e2e` (run 1) | **did not start**: API webServer timeout 180 s — synthetic generation alone took 2m06s (normally ~6 s); machine had ~1.1 GB of 8 GB RAM free | environment; no test ran |
| 2026-10-27 | D2-4 | `pnpm e2e` (run 2, dev servers stopped) | **did not start**: `next build` inside the web webServer exceeded 300 s | environment; no test ran |
| 2026-10-27 | D2-4 | `LUMIANT_API_ORIGIN=http://127.0.0.1:8100 pnpm build` then `playwright test -c playwright.local.config.ts` (uncommitted: same suite, prebuilt production app, 600 s startup timeouts) | build 3m13s OK · **20 passed** (16 existing unchanged + 4 new: palette, shortcuts+rail, ISSUES #10 background tab, reduced motion) | CSP no-violation test green |
| 2026-10-27 | D2-5 | `pnpm audit` | **No known vulnerabilities found** |  |
| 2026-10-27 | D2-6 | Screenshot script (Playwright, production build): dark/light 1440, palette, provenance, collapsed rail, mobile 390 dark/light, reduced motion | collapsed rail 68 px; mobile horizontal overflow 0 px (both themes); reduced motion: `.rise` animation `enter-fade` only, 0 faded elements. **Found**: palette input showed the global focus ring → scoped `[cmdk-input]` exception + focus-within border (moving the global rule to `@layer base` was rejected: it would remove the ring from 3 page inputs using `outline-none`) | screenshots in the session notes folder |
| 2026-10-27 | D2-7 | Rebuild + `playwright test -c playwright.local.config.ts` after the focus fix | full suite **19 passed, 1 failed**: `admin: schema check…` timed out (15 s) waiting for `schema-result`; probe showed `/api/admin/schema` answered after ~32 s queued behind the overview's in-flight API calls with ~0.5 GB RAM free (direct call 2 s). Rerun of that test alone with servers freed: **passed** (9.0 s). Same suite was 20/20 one run earlier; the diff in between is CSS/className only |  |
| 2026-10-28 | D2-8 | `playwright test -c playwright.local.config.ts` on the existing build | **20 passed** | later found to be a stale build (next row): the CSS lacked the last focus-ring change |
| 2026-10-28 | D2-8 | Screenshot re-shoot + `grep cmdk-input .next/static/chunks/*.css` | palette still showed the focus ring; **built CSS did not contain the `[cmdk-input]` rule or the new `focus-within:` class although `globals.css` predates the build** (earlier CSS edits were present) → Turbopack persistent build cache served stale CSS | ISSUES #33 |
| 2026-10-28 | D2-8 | `rm -rf .next/cache` then `LUMIANT_API_ORIGIN=http://127.0.0.1:8100 pnpm build` | build 2m33s; rule present in the CSS | |
| 2026-10-28 | D2-8 | `playwright test -c playwright.local.config.ts` (fresh build, final code) | **20 passed** (2.8 m) | |
| 2026-10-28 | D2-8 | Screenshot script on the fresh build | collapsed rail 68 px, mobile overflow 0 px (dark/light), reduced motion `enter-fade` only, 0 faded; palette shows focus through its row border, no ring | screenshots replaced in the notes folder |
| 2026-10-28 | S04-1 | Part B worktree: `ruff`, `format --check`, `mypy`, `pytest -q`; web `lint`/`typecheck`/`test` | **clean · 343 passed, 6 skipped · 23 web unit** | before merging |
| 2026-10-28 | S04-1 | Merged `main` (B ff + D cherry-pick): API `pytest -q`; web lint/tsc/unit; `playwright test -c playwright.prebuilt.config.ts` (temporary config serving a prebuilt bundle) | **343 passed · clean · 41 · e2e 20/20** | `pnpm e2e`'s in-config build exceeds the 300 s start-up timeout on this machine |
| 2026-10-28 | S04-2 | GitHub Actions on `f4e72d9` | api, api-postgres-redis, web, docker **green**; **e2e failed** (one test, 118 s step) | no detail without sign-in |
| 2026-10-28 | S04-3 | `edf701c` (Playwright `github` reporter on CI) → check-run annotations via public API | palette test: `locator.click` timeout waiting for the "Ask:" option | |
| 2026-10-28 | S04-4 | `592e365` (wait for focused input) → annotation | `toBeFocused` failed: palette input "inactive" after reopening (CI/Linux only; 5/5 and 3/3 at 6× CPU throttle locally) | real focus bug, not a test race |
| 2026-10-28 | S04-5 | `668216e` (explicit focus + stale focus-scope guard) | **all five jobs green** | |
| 2026-10-28 | S04-6 | Part C: `pytest tests/integration/test_agent_context.py`; `test_agent.py` with 8 new eval cases; full `pytest -q` | **24 passed · 47 passed · 375 passed, 6 skipped** | 4 first-run failures fixed (follow-up routing order, "top 10" missing from evidence, test scope, SSE context token) |
| 2026-10-28 | S04-7 | Web: `pnpm test` (+ `analyst.test.tsx`); lint; tsc | **50 passed · clean · clean** | |
| 2026-10-28 | S04-8 | Full e2e on a fresh build (23 tests incl. 3 Analyst tests) | **22/23**: `inventory search, filters and paging` lost `warehouse=3100` → explorer pending-URL fix → **23/23** | ISSUES #35 |
| 2026-10-28 | S04-9 | Browser (dev servers, alpha.admin, 1440×900): overview + insights, Analyze → dock trace/answer, Lens hover/select, dock reflow; SSE through the Next proxy timed in the page | works; first `step` at 16 ms, tool `block` at 688 ms, `answer` at 700 ms, no `content-encoding` | dev server first served stale CSS from `.next/dev` → cleared; KPI tiles too narrow beside the dock → container-query grids |
| 2026-10-28 | S04-9 | `uvx pip-audit` (with google-genai 2.27.0) · `pnpm audit` | **0 known vulnerabilities** both | |
