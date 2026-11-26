# Work Log

Append-only. Newest entry at the bottom. Template in `../00-context/CONTEXT_FLOW.md` §B.

---

## 2026-10-26 · S01 · Phase-1 · Investigation
- **Goal:** Investigate the repository before any coding (brief §24).
- **Done:** Listed the working directory (empty, not a git repo). Checked toolchain: Node 22.20, pnpm 11.10, npm 11.8, uv 0.11.15 with CPython 3.13.13/3.12.13, git 2.50, Java 24. Missing: Docker, WSL, PostgreSQL, SQL Server, Oracle tools, system python. Machine: 8 logical CPUs, 7.8 GB RAM, ~235 GB free on E:. Checked latest versions on npm and PyPI (see `00-context/ENVIRONMENT.md`).
- **Files changed:** none.
- **Commands + results:** `ls -la` → empty; `git status` → not a repo; `npm view <pkg> version` ×24; PyPI JSON for 17 packages; `uv python list --only-installed`.
- **Decisions:** Pin TS 5.9.3, DuckDB 1.5.x, SQLAlchemy 2.0.x pending spike (→ ADR-0005).
- **Issues / limitations:** No local enterprise DB available → connectors other than DuckDB cannot be tested here (→ ISSUES #1).
- **Next:** Plan approval.

## 2026-10-26 · S01 · Phase-1 · Plan approved
- **Goal:** Agent analysis, value-adds, roadmap, M1 scope.
- **Done:** Plan written and approved on the second submission. The owner asked that all knowledge, flow and logs be kept as Markdown in the repo → knowledge-base section added to the plan.
- **Decisions:** ADR-0001 … ADR-0006.
- **Next:** M1 step 1.

## 2026-10-26/27 · S01 · M1-step-1 · Repo + knowledge base
- **Goal:** `git init` and a complete knowledge base before code.
- **Done:** `git init -b main`. Wrote `docs/` (context, product, architecture + 6 ADRs, security, domain, plan, operations, customer questions, logs). The session was interrupted part-way (four security/domain doc writes were rejected); resumed on 2026-10-27 with "continue and complete the work" and the missing files were rewritten.
- **Files changed:** `docs/**`.
- **Commands + results:** `git init -b main` → initialized.
- **Decisions:** none new.
- **Issues / limitations:** `DEV_SETUP.md` and `TESTING.md` are written once real commands exist (step 3+).
- **Next:** Root files, then the dependency spike (step 2).

## 2026-10-27 · S01 · M1-step-1 · Root files
- **Done:** `CLAUDE.md` (imports CURRENT_STATE), `AGENTS.md`, `.gitignore`, `.editorconfig`, `.gitattributes`, session log `logs/sessions/2026-10-26-session-01.md`, `CURRENT_STATE.md`.
- **Next:** Spike.

## 2026-10-27 · S01 · M1-step-2 · Dependency spike
- **Goal:** Prove duckdb 1.5 + duckdb-engine 0.17 + SQLAlchemy 2.0 do what the query core needs.
- **Done:** Scratch script (outside the repo) built a DuckDB file with SAP-style DECIMAL columns, compiled a grouped/filtered SQLAlchemy select, executed read-only, attempted a write, interrupted a long query, parsed the SQL with sqlglot.
- **Files changed:** ADR-0003 status, ADR-0005 spike table.
- **Commands + results:** `uv run --no-project --with duckdb<1.6 --with duckdb-engine==0.17.0 --with sqlalchemy<2.1 --with sqlglot==30.25.0 python spike.py` → PASS after two script fixes (see ADR-0005).
- **Decisions:** Pins confirmed. LIKE escape char = `!` (backslash breaks on DuckDB via the PG dialect). Rollback the connection after an interrupt or error.
- **Issues / limitations:** none new.
- **Next:** Step 3 — API core.

## 2026-10-27 · S01 · M1-step-3 · API core
- **Goal:** Settings, logging, errors, request context, tenant config, canonical catalog, mapping resolver.
- **Done:** `services/api` uv project (Python 3.13, pinned deps). `core/` (fail-fast settings with production guards, JSON logging with request/user/tenant context, safe error envelope, request-id + security-header middleware). `auth/permissions.py`. `canonical/catalog.py` (10 datasets, field metadata, approved joins, computed `stock_value`). `tenancy/` (strict Pydantic schema + cross-validation + registry). `mapping/resolver.py` (canonical → SQLAlchemy tables, attributes as `attr_*`, schema-qualified sources). Two tenant YAMLs (`demo-alpha` SAP-style, `demo-beta` snake_case in `inv` schema, EUR+GBP).
- **Files changed:** `services/api/pyproject.toml`, `.env.example`, `config/tenants/*.yaml`, `src/lumiant/{core,auth,canonical,tenancy,mapping}/**`, `tests/unit/test_{config,tenancy,mapping}.py`.
- **Commands + results:** `uv sync` → ok; `uv run pytest -q` → 27 passed; `ruff check` → 11 findings fixed (1 manual rename); `ruff format`; `mypy` (strict) → 7 typing errors fixed → clean.
- **Decisions:** Extension attributes are addressed as `attr_<name>`; computed fields can't be mapped; customer tenants may not define dev users; connection paths must stay inside the API directory.
- **Issues / limitations:** none new.
- **Next:** Step 4 — synthetic generator.

## 2026-10-27 · S01 · M1-step-4 · Synthetic data
- **Goal:** Deterministic synthetic warehouses for two tenants with different physical schemas.
- **Done:** `synthetic/profiles.py` (7 item groups, warehouse specs matching tenant YAML), `generator.py` (seeded `random.Random`, `Decimal`; per item–warehouse event simulation over N months: receipts create lots and update moving weighted average, FIFO issues skip expired lots, internal transfers, ± adjustments, returns; balances derived from movements; customer-style reorder policies; planted scenarios), `writer.py` (maps canonical records onto the tenant's physical tables through `TenantMapping`, bulk loads via CSV `COPY`, `_dataset_info` + freshness table, atomic replace), `cli.py` (`lumiant-synthetic generate --all | --tenant`). Refuses non-synthetic tenants.
- **Files changed:** `src/lumiant/synthetic/*`, `tests/conftest.py`, `tests/unit/test_synthetic.py`, `pyproject.toml` (E501 ignored in tests for SQL strings).
- **Commands + results:** `uv run lumiant-synthetic generate --all` → alpha 600 items, 81,935 movements, 1,160 stock lines in 3.8 s; beta 250 items, 32,686 movements, 454 stock lines in 2.1 s. `uv run pytest -q` → 43 passed (16 new). ruff → 20 findings fixed; mypy → 3 fixed → clean.
- **Decisions:** Valuation price = generator's own MWA per item–warehouse, rounded half-even to 4 dp. ABC class is a synthetic stand-in for a customer-maintained field (80/95 % cumulative value with 5 % drift) — not a rule. Max stock kept ≥ 1.1× on-hand except planted over-stock pairs (first run had 11 % above max — unrealistic).
- **Issues / limitations:** Regenerating requires the API to be stopped (DuckDB file lock) — documented in DEV_SETUP.
- **Next:** Step 5 — connector + query engine.

## 2026-10-27 · S01 · M1-step-5 · Connector + query engine + audit
- **Goal:** The single secured path to data: plan → validate → compile → guard → read-only execute → provenance → audit.
- **Done:** `auth/principal.py` (Principal, WarehouseScope, dev-user → principal). `connectors/` (protocol with no string-SQL entry point; DuckDB connector: read-only engine, timer + `interrupt()` timeout, rollback after errors, safe error codes; per-tenant registry). `query/plan.py` (strict QueryPlan, floats rejected, `AnyOf` groups), `validator.py` (all rules in QUERY_ENGINE.md §2 incl. scope injection, explicit out-of-scope → 403, cost-field check across select/filter/aggregate, currency/UoM companions auto-added, stable default ordering), `compiler.py` (SQLAlchemy Core, outer joins on approved paths only, bound params, `!` LIKE escape, limit+1, count-only variant), `sql_guard.py` (sqlglot: one SELECT, function allowlist, mapped tables + CTEs only, system objects refused), `service.py` (QueryService: tenant meta with synthetic marker + freshness, execution, provenance, warnings, audit), `results.py` (Decimal → string envelope). `audit/store.py` + Alembic migration 0001 (fail-closed writes, no values stored).
- **Files changed:** `src/lumiant/{auth/principal.py,connectors/*,query/*,audit/*}`, `alembic.ini`, `alembic/**`, `tests/conftest.py`, `tests/helpers.py`, `tests/unit/test_validator.py`, `tests/unit/test_compiler_and_guard.py`, `tests/integration/test_query_service.py`, `pyproject.toml` (line length 120).
- **Commands + results:** first full run 98 passed / 6 failed → fixed → **104 passed**; ruff clean; mypy strict clean.
- **Decisions / findings:**
  - **Bug caught by the independent-SQL test:** SQLAlchemy's `Numeric(18,4)` result processing rounded aggregated values to 4 dp (e.g. `146708.07823930` → `146708.0782`). Output columns now use an `ExactDecimal` type with no result processing, so values arrive exactly as the database computed them.
  - DuckDB refuses a second in-process connection to the same file with a different config; duckdb-engine sets `custom_user_agent`. Test raw-SQL connections mirror it (`tests/helpers.py`). Production is unaffected (only the connector opens the file).
  - The SQL guard must parse SQL rendered with the connector's own dialect (`$n` params); `pyformat` params from a bare dialect don't parse.
  - Master-data datasets without a warehouse key (item, supplier, department) are tenant-wide, not warehouse-scoped.
- **Issues / limitations:** → ISSUES #5 (master data visible tenant-wide), #6 (row-limit only; no cost-based query planning).
- **Next:** Step 6 — auth, routes, metrics, below-reorder, API tests.

## 2026-10-27 · S01 · M1-step-6 · Auth, RBAC, routes, metrics, below-reorder
- **Goal:** Expose the query core over HTTP with server-side authentication and authorization.
- **Done:** `auth/provider.py` (DevAuthProvider: HS256 JWT in httpOnly SameSite=Lax cookie, claims sub/tid/iss/aud/iat/exp/jti, roles + scope re-resolved per request), `auth/deps.py` (current principal, `require(*permissions)` with audited denials, CSRF header check), `container.py`, `main.py` (app factory; refuses to start in OIDC mode until M6; docs disabled in production), `metrics/` (7 versioned draft metrics; value metrics warn about lines without valuation price), `analyses/below_reorder.py` (policy LEFT JOIN on-hand so zero-stock pairs appear; base-UoM only with mismatch warning; pairs without policy counted, never flagged), routes `api/{health,auth,meta,metrics,inventory,query}.py`.
- **Files changed:** `src/lumiant/{auth/provider.py,auth/deps.py,container.py,main.py,metrics/*,analyses/*,api/*}`, `src/lumiant/query/{results.py,sql_guard.py}`, `tests/integration/test_api.py`, `tests/unit/test_compiler_and_guard.py`.
- **Commands + results:** first run 127 passed / **6 failed** (guard refused `AND`/`OR` — sqlglot models them as `Func`); allowlist fixed + unit case added → **133 passed**; ruff + mypy strict clean.
- **Decisions:** `/api/health/ready` is unauthenticated, so it returns counts only. The inventory listing hides cost columns (and value sort) for users without `cost:read` instead of failing. Explicit filters on out-of-scope warehouses return 403 rather than an empty result (clearer for users, no information leak since ids are the caller's own input).
- **Issues / limitations:** Starlette deprecation warning for `httpx` in TestClient (→ ISSUES #8).
- **Next:** Step 7 — Next.js web app.

## 2026-10-27 · S01 · M1-step-7 · Next.js web app
- **Goal:** Login, permission-aware shell, overview dashboard, inventory explorer — on the secured API, with tests.
- **Done:** Scaffolded with `create-next-app@16.4.3` (TS 5.9.3, Tailwind 4 via the Turbopack loader, ESLint 9, `cacheComponents` + `partialPrefetching` defaults kept). Read the bundled Next 16 docs (proxy, cache components auth, instant navigation, flash prevention) before writing code. Built: `/api/*` rewrite to FastAPI (same-origin cookie), `src/proxy.ts` (optimistic redirect only), "ledger" design system (Archivo + IBM Plex Mono tabular figures, warm paper / graphite themes, hazard-tape SYNTHETIC badge, no-flash theme script), typed API client with safe error parsing, decimal-string formatting via `Intl.NumberFormat` (never floats), provenance "slip" popover (Radix), KPI strip (per-currency values, never summed), value bar charts with currency switcher, below-reorder table with coverage bars, inventory explorer (URL-state filters, debounced search, server sort/paging, cost columns hidden without `cost:read`).
- **Files changed:** `apps/web/**` (`next.config.ts`, `src/proxy.ts`, `src/app/**`, `src/components/**`, `src/lib/**`, `tests/unit/**`, `e2e/app.spec.ts`, `vitest.config.ts`, `playwright.config.ts`, `package.json`), `.claude/launch.json`, `services/api/src/lumiant/audit/store.py`, `services/api/tests/unit/test_audit_store.py`.
- **Commands + results:** `pnpm typecheck` / `pnpm lint` → clean. `pnpm test` → 14/20 then **20 passed** (test fixes: Intl NBSP, jsdom ResizeObserver stub). `pnpm exec playwright test` → 2/5, 3/5, 4/5, then **5 passed** (production build + isolated API on 8100 with freshly generated data). Manual checks in the browser pane: login, overview (alpha admin, analyst, beta admin, beta user), inventory filters/sort, light + dark, 375 px mobile (no horizontal scroll).
- **Bugs found and fixed:**
  1. **API first run crashed**: Alembic ran before the SQLite `var/` folder existed → `_ensure_sqlite_dir` + regression test `test_first_run_creates_missing_directory_and_schema`.
  2. **Hydration mismatch**: page content read the session query the shell had already resolved → `usePageMe()` reads it only after hydration.
  3. **Next 16 instant-navigation validation** dropped the page segment because the shell withheld children while the session loaded → the shell now always renders page content.
  4. **Stale-closure filter bug (found by e2e)**: the debounced search rebuilt the URL from a render-time snapshot and could wipe a warehouse filter chosen meanwhile → reads `window.location.search` at update time; e2e regression added.
  5. pnpm's release-age gate flagged `@tanstack/react-query@5.105.0` (published the day before) and auto-added an exclusion → exclusion removed, pinned 5.104.5, lockfile rebuilt so the gate passes.
- **Decisions:** Client-side data fetching (React Query) through the same-origin proxy; no server component reads cookies (keeps Cache Components simple and the API the only enforcement point). Chart bar lengths use numbers for geometry only; every printed amount is the exact decimal string.
- **Issues / limitations:** Entrance animations pause in background tabs (cosmetic). No CSP on the web app yet (→ ISSUES #9). Next keeps the previous route mounted but hidden (React Activity) — tests must scope locators to visible regions.
- **Next:** Step 8 — full checks, docs sync, report.

## 2026-10-27 · S01 · M1-step-8 · Close milestone
- **Goal:** Full check run, dependency audits, docs synced to the code, honest report.
- **Done:** Root `package.json` (data/dev/test/check scripts) and `README.md`; `DEV_SETUP.md`, `TESTING.md`; rewrote `CURRENT_STATE.md`; updated `ACCEPTANCE_CRITERIA` (rows 1–6, 10–18 verified for M1 scope; 7–9 pending M2/M3), `FEATURE_CATALOG`, `CONNECTORS` support matrix, `API_CONTRACTS`, `FRONTEND`, `QUERY_ENGINE`, `MAPPING`, `SYNTHETIC_DATA`, `SECURITY_PLAN` statuses, `ENVIRONMENT` resolved versions, `FACTS_ASSUMPTIONS` (F-011–F-013, A-010–A-011), decisions DEC-008–DEC-013, `CHANGELOG`. Removed two test warnings (enum in test, Vite config → `.mts`).
- **Commands + results:** `pnpm run check` → all green (134 API, 20 web); `pnpm audit` → 0; `pip-audit` → 0; e2e 5/5 (step 7).
- **Decisions:** DEC-008 … DEC-013 (see DECISION_LOG).
- **Issues / limitations:** First audit command was blocked by a safety check (temp file path outside the project); nothing ran; rerun with the session scratchpad.
- **Next:** Owner review + first commit (owner's call); then M2.

## 2026-10-27 · S01 · M2 · Intelligence engine
- **Goal:** Deterministic costing, computed ABC, item-code rules and the remaining risk analyses.
- **Done:** `costing/engine.py` (moving weighted average, periodic weighted average with `[start, end)` periods, FIFO layers + pick suggestion, latest valid purchase price, latest receipt cost; duplicate handling, zero quantities, negative stock/cost/sign errors, mixed currency/UoM refusal; rounding only in `present()`, half-even), `costing/abc.py` (no default cutoffs; cumulative share before the item decides the class), `costing/item_code.py` + tenant `item_coding` config (pattern + segments, nothing assumed), `analyses/below_reorder.py` generalised with `mode="excess"`, `analyses/risks.py` (dormant stock SQL analysis, expiring lots, data quality, computed vs assigned ABC, cost comparison with reconciliation against the source valuation), new join `stock_balance → lot`, routes `/api/analyses/{excess-stock,dormant,expiring-lots,data-quality,abc,cost-comparison}`, `risks` and `costs` sections in `/api/auth/me`. Web: Risks page (4 tabs) and Costs page (cost comparison, ABC), permission-aware navigation.
- **Files changed:** `services/api/src/lumiant/{costing/*,analyses/*,api/analyses.py,api/auth.py,canonical/catalog.py,tenancy/models.py,main.py}`, tenant YAMLs, `tests/unit/test_{costing,item_code}.py`, `tests/integration/test_m2_analyses.py`, `apps/web/src/{components/risks,components/costs,components/data/simple-table.tsx,lib/*,app/(app)/{risks,costs}}`, `apps/web/e2e/app.spec.ts`.
- **Commands + results:** `uv run pytest -q` → **177 passed**; ruff + mypy strict clean; `pnpm lint`/`typecheck` clean; Playwright **8 passed**.
- **Decisions:** All M2 definitions are `draft` until approved (D-002). The moving-average reconciliation tolerance is 0.0002 per unit because the source stores 4-decimal prices; differences beyond that are reported, never hidden. Computed ABC refuses to mix currencies (409) and has no default cutoffs. Costing reads movements through the same validated, scope-injected query path as everything else.
- **Verified hand-computed cases:** MWA 10@5 + 10@7 − 5 + 5@10 → 20 @ 7.00 = 140; FIFO on the same movements → 145; periodic average with boundary dates → 6.00; ABC 800/100/50/30/20 at 0.80/0.95 → A,B,B,C,C.
- **Issues / limitations:** Value mapping of movement types (`ISSUE`, `RECEIPT`…) is still canonical-only (ISSUES #3). ABC is limited to 1,000 items per request (large runs need background reports, M4/M6). Dormant/expiry use the data timestamp as "today".
- **Next:** M3 — AI agent.

## 2026-10-27 · S01 · M3 · AI agent
- **Goal:** Natural-language questions answered through the same secured query path, with no SQL from a model and no ungrounded numbers.
- **Done:** `agent/tools.py` (10 typed tools with pydantic argument models and permission lists; only permitted tools are ever shown to a model), `agent/providers.py` (`RuleBasedProvider`: deterministic matching incl. item and warehouse resolution, clarification choices, honest refusals e.g. obsolescence; `AnthropicProvider` via the official SDK with auto tool choice, capped/truncated model view and untrusted-data prompts; `build_provider` requires deployment config AND tenant approval), `agent/grounding.py` (numbers in prose must exist in results), `agent/service.py` (bounded ≤ 4 tool calls, AppError-safe tool runs, template fallback when model prose has ungrounded numbers or any tool failed, audit of every chat and of external disclosures, feedback), `api/agent.py` (`/api/agent/{suggestions,chat,feedback}`, `chat:use` permission, CSRF), tenant `ai.external_provider_approved` (default false), settings `agent_provider/agent_model/anthropic_api_key`, golden + adversarial eval sets in `services/api/evals/`. Web: Assistant page (suggestions, answers with tables and bars, clarification buttons, follow-ups, source slips, feedback, mode label).
- **Files changed:** `services/api/src/lumiant/agent/*`, `api/agent.py`, `container.py`, `main.py`, `core/config.py`, `tenancy/models.py`, `auth/permissions.py`, `api/auth.py`, tenant YAMLs (`chat:use`), `evals/*.yaml`, `tests/unit/test_grounding.py`, `tests/integration/test_agent.py`, `pyproject.toml` (+`anthropic` 1.17.0), `apps/web/src/components/assistant/*`, `apps/web/src/app/(app)/assistant`, nav, e2e.
- **Commands + results:** `uv run pytest -q` → **220 passed** (golden 14, adversarial 8, grounding 4, provider and endpoint tests); ruff + mypy strict clean; Playwright **11 passed**.
- **Bugs found by tests:** item token kept a trailing `?` so "for item X?" resolved nothing; model prose was allowed to overwrite a tool's "not available to your role" message (now any failed tool forces the template answer).
- **Decisions:** The default provider is the built-in matcher (AI-off mode works fully). External AI is used only if `LUMIANT_AGENT_PROVIDER=anthropic`, a key is set, and the tenant sets `ai.external_provider_approved: true`; otherwise the user sees a notice. Model default `claude-opus-5-5` (configurable). No forced `tool_choice` (unsupported on current models); no sampling parameters; thinking left at its default. Questions the tools cannot answer are declined with suggestions rather than guessed.
- **Not verified:** the Anthropic path has only been exercised against a fake client (request shape, tool filtering, grounding, fallbacks). It has never called the live API: no key was available and no customer has approved external AI (Q-013). → ISSUES #13.
- **Next:** M4 — guided menu, reports, exports.

## 2026-10-27 · S01 · M4 · Reports, exports and guided menu
- **Goal:** Reports with downloadable/printable output and a guided menu that calls the same secured services.
- **Done:** `reports/service.py` (6 report definitions built on the existing analyses and plans, metadata header with tenant, data as-of, filters, access scope, row count, truncation, synthetic and draft notices; CSV with BOM and `#` metadata lines; XLSX via openpyxl; formula-injection neutralisation; decimals stay text), `api/reports.py` (`/api/reports`, `/{id}`, `/{id}/export`), `export:data` permission (not granted to the no-cost viewer role), exports audited. Web: Reports page (preview, window parameter, CSV/Excel/Print, metadata block, print stylesheet), Explore page (8 permission-filtered guided cards that open pages or ask the assistant), assistant accepts `?q=`.
- **Commands + results:** `uv run pytest -q` → **234 passed** (+14 report tests incl. raw-SQL parity, scope disclosure, role gating, tenant isolation, formula injection, audit); ruff + mypy strict clean; Playwright **12 passed**.
- **Decisions:** Export is a separate permission from viewing. Exports include up to the tenant row limit and say so when truncated; previews show 200 rows. Spreadsheet cells never contain computed floating-point numbers; amounts remain exact text.
- **Not done (moved to M5):** drill-through from charts, saved views, report scheduling and background generation for very large reports, editable query chips.
- **Next:** M5 — admin and onboarding.

## 2026-10-27 · S01 · M5 · Admin and onboarding
- **Goal:** Tools to onboard a source safely: detect mapping drift, show what a mapping unlocks, prove numbers against the customer's own report, review access.
- **Done:** `admin/service.py` (schema discovery comparing mapped columns and type categories with the source: missing table/column, type mismatch, unmapped candidate columns; capability matrix of 12 capabilities with the exact missing fields; reconciliation of the value-by-warehouse report against a pasted customer report, per currency, with a tolerance and a go-live verdict; tenant-scoped audit explorer with decision/action filters), `AuditStore.search`, `api/admin.py` (`/api/admin/{schema,capabilities,audit,reconciliation}`; `admin:tenant`, `audit:read`, `cost:read` + CSRF), `admin` section. Web: Admin page with four tabs.
- **Commands + results:** `uv run pytest -q` → **244 passed** (+10 admin tests: no drift on both generated warehouses, injected drift detected, capability gaps explained, role gating, reconciliation pass/variance/missing/currency-mismatch, audit scoping and filter validation); ruff + mypy strict clean; Playwright **14 passed**.
- **Decisions:** Discovery reads metadata only. Reconciliation is a gate, not an adjustment: it never changes data. A figure reported in the wrong currency does not match.
- **Not done:** value maps (e.g. source `ROH` → canonical `RAW`), mapping editor/approval workflow, AI-suggested mappings, column profiling, saved views, drill-through, editable query chips, tenant glossary. These remain open (ISSUES #3, #15).
- **Next:** M6 — hardening and deployment preparation.

## 2026-10-27 · S01 · M6 · Hardening and deployment preparation
- **Goal:** Close what can be closed without the customer: abuse limits, browser security headers, a real customer-IdP authentication path, packaging, CI, and an honest readiness statement.
- **Done:** `core/ratelimit.py` sliding-window limiter and `rate_limit`/`rate_limit_by_ip` dependencies on chat, query, export and sign-in (429 with `Retry-After`; configurable; per-process). `auth/oidc.py`: bearer-token validation with PyJWT + JWKS (asymmetric algorithms only), tenant chosen by issuer + audience, IdP groups mapped to roles and warehouse scope from tenant YAML (`oidc:` block, validated), no-role users refused (`no_access`), verification failures never leak details; OIDC mode now starts instead of refusing (still refuses when no tenant is configured). Web: strict Content-Security-Policy (no eval in production, no framing, no plugins, same-origin connections), login page explains SSO mode. Packaging: API and web `Dockerfile`s, `docker-compose.yml` (local demo), `.dockerignore`, optional `postgres` extra, `.github/workflows/ci.yml`. Docs: `PRODUCTION_READINESS.md`, rewritten `DEPLOYMENT.md`, `RUNBOOK.md`, `USER_GUIDE.md`, `ADMIN_GUIDE.md`.
- **Commands + results:** `uv run pytest -q` → **266 passed** (+16 OIDC incl. key-confusion/alg-none/expired/wrong-audience/no-group, +6 hardening); ruff + mypy strict clean; Playwright **15 passed** on the production build with the CSP (no violations); `pip-audit` / `pnpm audit` clean.
- **Findings:** PyJWT refuses to sign HS256 with a PEM key, so the key-confusion test hand-builds the forged token. In the rate-limit work the shared test client logged in more than the sign-in limit, so tests set a high default via environment while limit tests set explicit small values.
- **Not verified:** OIDC against a real IdP (Q-010), Docker builds, the GitHub Actions workflow, PostgreSQL, a shared rate-limit store across replicas, nonce-based CSP. All are recorded in `PRODUCTION_READINESS.md`.
- **Next:** hand over: the remaining work is customer-dependent (M7) or the open items in ISSUES.

## 2026-10-27 · cloud-verify · Linux verification and hardening
- **Goal:** Do on Linux what the Windows machine could not: full checks, e2e, Docker, workflow validation, PostgreSQL, and close ISSUES #18/#19.
- **Environment:** cloud sandbox (Linux, Docker Engine 29.9 daemon started by hand, PostgreSQL 16, Redis 7.0.15). Outbound network is allow-listed: `cdn.playwright.dev` and `ghcr.io` blobs are blocked, Docker Hub rate-limits (429); PyPI/npm work.
- **Done:** (1) API checks all green (266 passed), web lint/typecheck/20 unit green, e2e 15 passed on the preinstalled Chromium (the official browser download is blocked, ISSUES #21). No Linux-only defects. (2) Built both images and ran compose: **found and fixed** a real bug (non-root user could not write `/app/data`; now `/data`, owned, `LUMIANT_DATA_DIR`); also installed the `redis` extra in the image. Sign-in and overview verified in a browser. (3) `actionlint` clean; fixed the `pnpm/action-setup` version/`packageManager` conflict; added PostgreSQL+Redis and Docker jobs. (4) PostgreSQL 16: migration up/down/up and the full API suite pass; test helper `app_db_url` gives each test app a fresh PostgreSQL database when `LUMIANT_TEST_PG_ADMIN_URL` is set; added a PostgreSQL audit-store test. (5) `Limiter` protocol + `RedisRateLimiter` (atomic Lua sliding window, server clock, in-process fallback on outage, URL is a secret) with tests against a real Redis; nonce CSP in `src/proxy.ts` + external `theme-init.js`, per-request rendering (`cacheComponents` off) — ADR-0007.
- **Commands + results:** see TEST_RUNS CV-1…CV-6. Final: API 269 passed + 6 env-gated skipped (275 with PostgreSQL and Redis), web unit 23, e2e 16, ruff/mypy/eslint/tsc clean, audits 0 findings.
- **Findings:** static prerendered shell cannot carry a CSP nonce (confirmed by inspecting the served HTML before the fix); PG ≥15 does not let a non-owner create tables in `public`.
- **Not verified:** GitHub Actions run of the workflow; builds against the real ghcr/Docker Hub images; production-mode container with a real OIDC IdP and PostgreSQL; managed Redis/PostgreSQL; `playwright install --with-deps` and the matching Chromium build; all customer-dependent items.
- **Next:** push `cloud-verify`, open a PR when the owner wants one, watch the first GitHub Actions run.

## 2026-10-27 · S02 · CI · First GitHub Actions run failed on mypy
- **Goal:** Make the first GitHub Actions run of `ci.yml` green.
- **Finding:** run #2 on `f437fdf`: `ci / api` failed at `uv run mypy` (ruff and format passed; `e2e` skipped because it needs `api`). `core/ratelimit.py:97` imports `redis`, which is an optional extra; the `api` job runs `uv sync --frozen` without extras, and mypy strict had no override for it → `import-not-found`. `api-postgres-redis` passed because it installs the extra. Reproduced locally with the same command.
- **Done:** `pyproject.toml`: `redis`, `redis.*` added to the existing `ignore_missing_imports` override. When the extra is installed, `redis` ships `py.typed`, so its real types are still checked.
- **Commands + results:** see TEST_RUNS S02-1. Without extras and with `--extra redis --extra postgres`: ruff clean, 96 files formatted, mypy 70 files OK, 269 passed + 6 env-gated skips.
- **Next:** push, watch the run (first run of `e2e` on GitHub).
- **Result:** pushed `3ef74b9`; GitHub Actions run green in all five jobs, including the first GitHub run of `e2e` and the `docker` job on real upstream images (TEST_RUNS S02-2). ISSUES #17, #21, #22 closed.

## 2026-10-27 · S03 · M8 · Client SAP data intake (plan Part B)
- **Goal:** Load the two real client SAP exports locally (never committed) through a strict importer, extend the platform for what the data needs, and build a synthetic twin with the same layout for CI/demos.
- **Authorization:** owner decision relayed by the coordinating session: real files only on the owner's machine under `services/api/var/private/`, never committed, no real values in code/logs/docs (recorded in `sessions/2026-10-27-session-03.md`).
- **Done:** B1 explicit `.gitignore` lines for `var/private/` and XLSX + `test_private_data_guard.py` (`git check-ignore`, nothing tracked). B2 `ingest/sap_exports.py` + `lumiant-ingest sap` (header contract, codes as text, exact decimals, SAP total rows as control totals with a hard gate, master checks, exact unit price, manifest, atomic DuckDB with raw tables + views, generated tenant YAML). B3 `customer_extract` classification (ADR-0008: private tenant dir, dev + flag, production refusal, badge, CONFIDENTIAL exports, external AI off); canonical `stock_status`, `source_value`, `price_rounding`, dataset `item_warehouse`; value maps compiled to CASE (closes ISSUES #3); explorer/reports/metrics request only mapped fields; SAP data-quality checks; capability `needs_file`. B4 `demo-gamma` twin (XLSX in client layout → same importer, planted anomalies). B5 tests. B6 `07-customer/CLIENT_DATA_INTAKE.md`, ADR-0008, Q-019…Q-026. Web: `DataBadge` (client-extract badge), login/provenance labels, DQ `info` status + share, explorer stock-status filter, hidden absent columns.
- **Commands + results:** TEST_RUNS S03-1…S03-15. Final: API **343 passed + 6 env-gated skips**, ruff/format/mypy clean; web lint/typecheck clean, unit 23, e2e 16 (alternate ports). Real import: gate passed, no line beyond the price-rounding bound, no private files in `git status`.
- **Findings:** (1) the SQL guard refused CASE (sqlglot `If` nodes) — allowed explicitly. (2) Descriptive fields (`warehouse.name`, `lot_id`) broke reports/metrics for sources without them — now optional. (3) On the real files a plain 0.01 tolerance made SAP price rounding look like value mismatches; SAP stores the value and shows the price rounded per price unit, so the rule is now 0.01 + \|qty\| × 0.005 ÷ price unit. (4) The earlier profile's "one duplicate key" was not reproduced (ISSUES #27).
- **Decisions:** DEC-015…DEC-018 (ADR-0008, value-map compilation, `item_warehouse`, control-total gate).
- **Not done / not verified:** assistant tools for SAP tenants (ISSUES #29, Part C); overview ABC tile for plant-level ABC (#28); client meanings of codes (Q-019, Q-022); browser check of the client-extract badge on real data was not run (covered by API tests and the web type/unit checks).
- **Next:** owner reviews the branch; send Q-019…Q-026 and request MB51/MSEG, MARC, MCHB/MCH1, T001W/T001L, EKPO; Part C (agent) builds on the canonical changes.

## 2026-10-27 · Part D1–D2 · Command-center design system and shell
- **Goal:** plan Part D1–D2 (`c-users-windows-downloads-warehouse-sto-golden-snowglobe.md`): dark-first design system, motion system, ISSUES #10, new shell with ⌘K palette. Frontend only; `services/api` and `shell/synthetic-tape.tsx` untouched (owned by Part B).
- **Done:** branch fast-forwarded to origin/main (dd3afd6). D1: `globals.css` rewritten (dark default, light opt-in; planes, ink, lines, control-line, accents; glass + elevation + glow; ambient layer; dataviz palette and status tokens; motion and z variables; `panel`/`glass` utilities; `light:`/`rail-collapsed:` variants); Geist Sans/Mono self-hosted via `next/font/local` (`geist` package); `lib/motion.ts` constants mirrored in CSS; reduced-motion branches (CSS fade, `MotionConfig reducedMotion="user"`); ISSUES #10 fixed in `public/theme-init.js` (+ Motion skip while hidden). D2: `app-shell.tsx` rebuilt (collapsible icon rail with groups, sliding active marker, pending dot, tooltips; glass command bar keeping tenant, synthetic badge and data-as-of slots; mobile bottom tab bar; route fade), `command-palette.tsx` (cmdk + Radix Dialog + Motion: pages by `Me.sections`, materials via the existing balances search, "Ask: …", actions), `use-shortcuts.ts`, `nav.ts`, `rail-state.ts`, `lib/ask.ts`; explorer mirrors outside URL `q` changes into its search box; assistant accepts palette questions in place. Shared primitives restyled (Panel, Warnings, Skeleton, Provenance, SimpleTable, Pager, ValueBars, KpiStrip) with unchanged behaviour and test ids.
- **Commands + results:** TEST_RUNS D1-1…D2-7. Final: lint/typecheck clean, unit 41 passed, e2e 20 passed (production build; prebuilt because the machine was memory-starved), audit 0, token-lint 0.
- **Decisions:** DEC-019 (dark-first, separate UI/data color sets, Geist local), DEC-020 (CSS entrances + Motion for interaction only; palette reuses permission-scoped endpoints). No e2e text or test id changed; 4 e2e tests added.
- **Findings:** cmdk's default fuzzy scorer matches typed questions to page names; unlayered global focus ring is intentional (it protects inputs that use `outline-none`).
- **Not done / limits:** pages still use hand-built `animationDelay` ladders (D4); palette material search depends on the stock-line endpoint (ISSUES #32); dev-only nonce hydration warning (ISSUES #31, pre-existing); Part B's `DataBadge` header change must be re-applied on merge (notes folder `part-d1-d2-shell.md`). Not committed (owner decides).
- **Next:** D3 (Analyst Lens) after Part C APIs; D4 pages.

## 2026-10-28 · Part D1–D2 · Completion
- **Goal:** owner asked to complete the work: a clean e2e run on the final code and screenshots that show the last fix.
- **Done:** found that the build used for the last runs was stale (Turbopack persistent build cache, ISSUES #33): its CSS lacked the palette focus change. Cleared `.next/cache`, rebuilt, ran the full suite on the fresh build (**20 passed**), re-shot all screenshots (palette now without the stray ring). TESTING.md: e2e count 20, cache and low-memory notes.
- **Commands + results:** TEST_RUNS D2-8.
- **Not done:** nothing in D1–D2 scope. Not committed (owner decides). Merge with Part B still needs the `DataBadge` line re-applied in `app-shell.tsx`.

## 2026-10-28 · S04 · Integration of Parts B + D1–D2, CI e2e fixes, Part C (M9) and Part D3/D4 (M10)
- **Goal (owner: "complete the work and push the code"):** bring the two side sessions' work onto `main`, keep CI green, then build plan Parts C and D3/D4.
- **Integration:** Part B committed by its session (`b4aecb8`), fast-forwarded onto `main`; Part D1–D2 committed (`1eed151`) and cherry-picked as `f4e72d9` with conflicts resolved (app shell keeps both the command bar and the client-extract `DataBadge`; log files keep both sides, D's ISSUES #23–25 → #31–33 and DEC-015/016 → DEC-019/020). Verified on the merged tree before pushing: API 343 passed, web unit 41, e2e 20/20 (prebuilt bundle; the in-config build exceeds the start-up timeout on this machine). Real client import re-run in the main folder: gate passed, nothing private tracked.
- **CI e2e (first GitHub run with D's tests) failed** on the command-palette test. Logs need sign-in, so the Playwright `github` reporter was added on CI (`edf701c`); its annotation showed the palette input not focused after reopening on Linux. Fix: explicit focus on open + a frame later, and a closing palette's focus scope no longer restores focus while the palette is open again (`668216e`); the test now waits for the focused input before typing (`592e365`). CI green on all five jobs.
- **Part C (M9):** `GeminiProvider` (`google-genai` 2.27, automatic function calling off; ADR-0009); `ChatRequest.context` + `history` (validated, scope-checked, narrowing only; labels never trusted; ADR-0010); matcher routes vague questions about selections and short follow-ups; `only` comparisons and narrowing filters on `stock_by` / `top_value_items`; new tools `concentration` and `insights`; `POST /api/agent/chat/stream` (SSE); insight engine + `GET /api/insights` with capability gaps naming the missing SAP data; 24 new tests + 8 eval cases.
- **Part D3/D4 (M10):** Analyst Lens — analyzable KPIs, value panels, bars, explorer rows and insight cards; Lens mode (`L`), persistent resizable dock (⌘J) with streamed trace, answers, pins; insight feed on the Overview ("command center"); assistant page on the shared streamed renderer; container-query grids so the page reflows beside the dock.
- **Found and fixed:** explorer debounced search could still wipe a just-chosen filter when `router.replace` had not committed yet (ISSUES #12 regression exposed by slower row rendering; now tracks the pending URL). Dev server served stale CSS from `.next/dev` (same class as ISSUES #33).
- **Commands + results:** TEST_RUNS S04-1…S04-9. Final: API 375 passed + 6 env-gated skips; ruff/format/mypy clean; web lint/tsc clean, unit 50; e2e 23/23; pip-audit and pnpm audit 0 findings.
- **Not done:** live Gemini call (needs the owner's key in `.env` and an approved synthetic tenant; ISSUES #13); D4 rest (virtualized inventory grid, Material 360, Risks/Costs/Reports/Admin restyle, Admin › Data sources); axe run.

## 2026-10-31 · S05 · Audit, then three answer-integrity fixes
- **Goal:** owner asked for a read-only enterprise audit of `647ef7b`, then asked to fix the three defects that show wrong figures.
- **Done:** 14 audit documents in `docs/` (start at `CODEBASE_AUDIT.md`). Fixed ISSUES #40 expiry counts (counted in the source, not from capped rows), #41 failed insight rules (`failed` + `complete`, never cached, Overview alert, no all-clear in chat), #42 unverified model text (withheld when no tool ran, shown as a failure in the UI, audited as `:blocked`).
- **Decisions:** the withholding applies only to model-authored text; built-in clarifications carry numbers from code and are unaffected. With no tool result, a figure the user typed is not evidence, so a model cannot confirm it. Corrected `test_expiring_lots`, which asserted the defect; it now compares with independent SQL.
- **Commands + results:** TEST_RUNS S05-1…S05-7. API 392 passed + 6 env-gated skips; web unit 55; e2e 23/23.
- **Not done:** grounding limits (audit LA-10), the other audit findings, live model test (ISSUES #13). `pnpm audit` reports one dev-only moderate advisory, which CI will likely flag. Not committed (owner decides).
- **Next:** `CODEBASE_AUDIT.md` §18.

## 2026-10-31 · S05 · No-mapping chat prototype
- **Goal:** owner wants a simple chatbot that works out the schema itself, with no user mapping. Build a prototype and measure it on the demo data.
- **Done:** `lumiant.nomap`, not wired into the API: discovery from the database itself, guarded SQL with per-user limits rewritten into the query, chat loop with number grounding, CLI. Evaluation in `services/api/eval/nomap`, on branch `prototype/no-mapping-chat`.
- **Result:** of 52 questions across 3 schemas, 49 right, 1 asked for clarification, 2 differ from the key by a disclosed SAR 882.20, none silently wrong. See `eval/nomap/RESULTS.md`.
- **Found:** `_dataset_info` lists the planted problems, so evaluation copies drop it. A 0.05% scoring tolerance hid the 882.20 difference, so scoring is now exact. A Snowflake table function passed the guard, now refused. SQL Server single-number queries work on this path (compare audit LA-51).
- **Not done:** live model loop (no API key), real SAP-sized schema, knowledge packs, reconciliation. ADR-0002 still stands: replacing it is the owner's decision. Not committed (owner decides).

## 2026-11-01 · S05 · Sign-out data leak fixed (ISSUES #43)
- **Goal:** owner asked to fix LA-39, where the next user in a tab could read the last user's Analyst answers.
- **Done:** `resetAnalyst` at sign-out and session expiry clears the conversation, selections, dock, lens and pins. `bindAnalystUser` empties the Analyst when the signed-in user changes, even without a sign-out. Pins are stored per user, and pins saved without an owner are dropped. An answer still streaming cannot reach the next user.
- **Decision:** pins are deleted at sign-out, not only hidden, because they hold cost values in browser storage. They were already described as a convenience, not a record.
- **Commands + results:** TEST_RUNS S05-11…S05-13. Web unit 61; e2e 24/24.
- **Not done:** a second tab left open keeps showing its page until its next request; every page has this, not only the Analyst. Not committed (owner decides).

## 2026-11-03 · S05 · No-mapping agent at ERP scale and on real engines
- **Goal:** owner's direction: the agent connects to different ERPs seamlessly and analyses data properly with minimal human setup. Keep solving the register and keep looking for new problems.
- **Done (prototype only, `lumiant.nomap`):**
  - On-demand discovery with table search, so 2,000 tables take 16 s instead of hours.
  - Statistics for scoped users are gathered within their limits.
  - Automatic health checks: duplicates, total rows, totals tables, mixed currencies and units, price per N units.
  - SAP knowledge pack.
  - Stored name case on every engine, `%` handling, and query timeouts on all drivers.
  - Live PostgreSQL check (`eval/nomap/live_postgres.py`) and a crowded 313-table test (`eval/nomap/crowded.py`).
- **Found and fixed:** LA-52 to LA-56 in `QUESTIONS_AND_LIMITATIONS.md`. A first version of the health checks gave false alarms and missed duplicates that differ only by a row number; both are fixed.
- **Results:** PostgreSQL 37 of 37 answer-key queries match DuckDB; crowded ERP 8 of 8 exact with a real model; 453 API tests pass. See `services/api/eval/nomap/RESULTS.md`.
- **Not done:** sampling for huge tables, joins on large databases, live SQL Server, Oracle, HANA or Snowflake, live `ask` loop, SAP pack confirmed on a real sandbox. Not committed (owner decides).

## 2026-11-04 · S05 · No-mapping agent on a real ERP (Odoo 18)
- **Goal:** owner asked to test the agent across different systems and to report where it works and where it falls short.
- **Done:**
  - Installed official Odoo 18 (stock, purchase, sale_stock, demo data) on the embedded PostgreSQL.
  - Computed the answer key with Odoo's own ORM.
  - A real AI session answered 12 questions through a read-only database login.
  - `--url` option on the CLI; read-only login refuses delete, update and create.
- **Result:** 8 exact, 2 defensible and stated (27 products vs 33 variants; 4 confirmed orders with nothing received vs 1 with an open receipt), 2 clarifying questions, 0 silently wrong.
- **Found and fixed:** LA-59 to LA-63 in `QUESTIONS_AND_LIMITATIONS.md`:
  - JSON columns broke profiling.
  - Odoo's mirror records were not flagged; there is now a cancel-out check.
  - Search under-weighted known meanings.
  - The CLI command name did not match the catalog text.
  - Added an Odoo knowledge pack.
- **Also found:** Windows' 260-character path limit silently dropped 1,299 Odoo files when extracted in a deep folder (LA-64). The Odoo session's transcript file was empty, so its isolation is self-reported.
- **Documents:** `reports/Lumiant System Test Report.pdf` (new) and `reports/Lumiant Pending Work.pdf` (redone).
- **Not done:** Odoo rerun with its pack; real SAP, Oracle Fusion, Dynamics; live SQL Server or Oracle. Not committed (owner decides).

## 2026-11-08 · S06 · Merged PR #3 (no-mapping chat prototype), conflicts resolved
- **Goal:** owner asked to pull, fix a merge conflict, complete the open PR, and push.
- **Done:** fast-forwarded local `main` to `origin/main` (10 commits: PRs #1, #2, #4, #5 already merged by `Saadahmed05` on GitHub). Merged PR #3 (`prototype/no-mapping-chat`, head `c18fedd`) onto the updated `main`; two conflicts, both in `docs/logs/TEST_RUNS.md` and `docs/logs/WORKLOG.md` — independent dated entries from diverging branches, resolved by interleaving in date order (no content dropped from either side). Verified on the merged tree, then pushed straight to `origin/main`, which closed PR #3 as merged (GitHub matched the carried-over head commit).
- **Commands + results:** TEST_RUNS S06-1.
- **Not done:** `lumiant.nomap` stays unwired (ADR-0002 unchanged); the owner has not yet decided whether to bring it into the product.

## 2026-11-11 · S07 · M11 visual refresh (graphite + emerald, Inter, system theme)
- **Goal:** owner asked for a premium look: new colour and font combination, every component engineered properly, plan first. Owner chose graphite + emerald, Inter + Geist Mono, theme follows the device. Plan approved; owner then said "complete the work now" and stopped the slow baseline run.
- **Done (web only, visual layer; no backend, route, wording, permission or test-id change):**
  - Tokens in `globals.css`: new values under the same names, radius rule, type scale, flat background; glow, grid and radial lights removed.
  - Inter variable self-hosted (`inter-ui` 4.1.1); numbers in Inter with aligned digits; Geist Mono only for identifiers.
  - Theme follows the device until the user chooses; "Theme: match system" in the palette.
  - New primitive layer `components/ui/`; shell, Analyst and all nine screens moved onto it.
  - `tests/unit/ui.test.tsx` (13 tests).
- **Found and fixed on the way:** caller classes fighting primitive classes (Costs input widths); light-theme critical red and warning label below 4.5:1; Inventory sorted by value pushed the VALUE column off-screen at 1440 px (columns now 24 px apart, numbers never wrap); a long money KPI ran past its tile on the SAR tenant (`.kpi-fit` shrinks it with the tile).
- **Commands + results:** TEST_RUNS S07-0…S07-7.
- **Deviations from the plan:** no baseline unit/e2e run and no "before" screenshots (owner stopped the baseline); no sticky table header (ISSUES #50); visual check from headless screenshots, not a real display (ISSUES #51); `ship-check` skill not run (its checks were run one by one); API tests not run (backend untouched).
- **Records:** ADR-0011, DEC-024/025, ISSUES #39 narrowed, #50–#52, FRONTEND, TESTING, USER_GUIDE, UI_UX_AUDIT note, CHANGELOG, IMPLEMENTATION_PLAN M11.
- **Not done:** owner's look on a real display; axe run; D4 rest. Committed and pushed to `main` at the owner's request; CI not yet checked.

## 2026-11-11 · S07 · CI fix and follow-ups of the refresh
- **Goal:** owner: "do all things by yourself, fix it" after the push.
- **Done:** CI had been red on `main` since the PR #3 merge: the no-mapping tests read the developer's untracked `data/synthetic`; a session fixture now generates that data (ISSUES #54). Sticky table header (#50). ABC values and reconciliation amounts formatted (#52). Command bar wraps below 1280 px so the SYNTHETIC label is never covered (#55). Live look in the in-app browser, dark and light (#51 partly).
- **Kept on purpose:** numbers in answer sentences stay exact for the grounding guard (owner's call to change).
- **Commands + results:** TEST_RUNS S07-8…S07-10. Committed and pushed at the owner's request.

## 2026-11-20 · S08 · Merge PR #6
- **Goal:** owner: "accept the PR, merge it, fetch the code locally".
- **Done:** PR #6 (Saadahmed05, "Fix assistant gaps and UI bugs found in the product audit" + "Agent: ERP and Arabic terminology layer") fast-forwarded onto `main` (`758153d..69a0ab4`) and pushed; GitHub shows it merged. No AI attribution in its commits; only dependency change is `opentelemetry-api` 1.45.1 → 1.45.2.
- **CI on the PR head:** api, api-postgres-redis, docker green; web lint/typecheck/unit green but `pnpm audit` red (7 moderate advisories in `next` 16.4.0–16.4.4, fixed in 16.4.5; not caused by the PR); e2e skipped.
- **Follow-up (owner: "Yes, bump next"):** `next` and `eslint-config-next` 16.4.3 → 16.4.5; audit clean, lint/typecheck/unit 78/build green (TEST_RUNS S08-1, S08-2).
- **Not done:** e2e and API tests not re-run locally; changes not committed.

## 2026-11-24 · S09 · Merge PR #7
- **Goal:** owner: "accept the pr and fetch code locally".
- **Done:** PR #7 (Saadahmed05, "Planning workspaces, official branding and customer commitment protection", 5 commits) merged on GitHub with a merge commit (`1ea5c0a`), same style as PRs #1–#5; local `main` fast-forwarded `4e4ca53..1ea5c0a`. 104 files, +10,828 / −109: new `lumiant.planning` package (BOM, MRP, suppliers, commitments, duplicates, obsolescence), `api/planning.py`, agent planning tools and small talk, synthetic `demo-delta` tenant, scenario evals, four web workspaces (Planning, Commitments, Suppliers, Master data), brand logo, ~35 new docs. No AI attribution in its commits; no `pyproject`/`package.json`/lockfile change, so no install needed.
- **Local verification (owner: "Run tests"):** API 787 passed + 6 env-gated skips, ruff/format/mypy clean; web lint/typecheck clean, unit 80; e2e 36/36 (29 existing + 7 planning) on a clean build cache. First e2e attempt was cut off mid-build by a session restart and rerun. Four "socket hang up" proxy lines during e2e (requests aborted by navigation); no test affected.
- **Commands + results:** TEST_RUNS S09-1…S09-5.
- **Not done:** topic docs, CURRENT_STATE and IMPLEMENTATION_PLAN not yet updated for the planning module; log changes not committed.

## 2026-11-25 · S10 · Product v2 plan (UI/UX, landing page, Analyst v2 on Gemini)
- **Goal:** owner: make Lumiant "next level": premium custom colours, far more visuals, easy and fast UX, a proper landing page, a fully working Gemini assistant with RAG over the data; "a product, not a prototype". Plan first.
- **Done:** read the worklog, `UI_UX_AUDIT.md`, `UI_UX_IMPLEMENTATION_STATUS.md`, web source and `agent/` source. Wrote `05-plan/PRODUCT_V2_PLAN.md`: honest gap table, design principles, visual identity v2 on the official palette, a chart kit (12 components), screen-by-screen plan incl. a public landing page, Analyst v2 (Gemini multi-step tool loop, `query_inventory(QueryPlan)` tool within ADR-0002, tenant-scoped knowledge index for definitions/policies/item text, chart blocks, streaming, threads, live eval gate), speed/accessibility budgets, productisation items, phases P1–P7 and decisions D1–D7. M12 added to `IMPLEMENTATION_PLAN.md` as proposed; docs map updated.
- **Findings:** Recharts is used in one component only; `/` redirects to `/overview` (no landing page); the model picks tools once per question (no chaining); `query_inventory` is allowed by ADR-0002 but not exposed to the model; `QueryPlan` has no time bucket, so trend charts need a new tested op.
- **Not done:** live look at the app this session: `api` and `web` dev servers stayed at "starting" for several minutes on this machine and were stopped (same class as ISSUES #33); the plan relies on earlier live reviews. No code changed. Nothing committed.
- **Next:** owner approves the plan and decisions D1–D7; owner puts the Gemini key in `services/api/.env` (never in chat); start P1 + P2.

## 2026-11-25 · S10 · P1 + P2 (owner: "Approve, start P1+P2"; then "loop until the session limit, find bugs, upgrade UI/UX, test and push")
- **P2 (API):** `GeminiProvider.advance` multi-step loop with limits in `AgentService` (think steps streamed as `think:N`); `agent/data_tools.py` (`query_inventory`, `catalog_note`); `lumiant.knowledge` (curated content, BM25 + optional Gemini embedding fusion) and `agent/knowledge_tools.py` (`search_knowledge`, `sources` block); offline matcher routes definition questions to it; `model_view` carries passages and failure status. ADR-0012, DEC-026.
- **P1 (web):** tokens v2 (`--ai`, sequential + diverging ramps with label colours, display sizes, page wash); chart kit `components/viz/` (ChartFrame + hidden data table, Sparkline, KpiCard/DeltaChip, TrendArea, ParetoChart, Treemap, StackedBars, RiskMatrix, Waterfall, HeatCalendar, Gauge, RadarChart, Timeline); `/design` showcase with labelled sample values; Analyst renders cited sources. DEC-027.
- **Bugs found and fixed:** circular import when `data_tools` loaded first (tools now self-register); hydration mismatch from locale month names; treemap labels unreadable on bright cells; waterfall changes invisible from a zero baseline; clipped timeline labels.
- **Commands + results:** TEST_RUNS S10-1…S10-5. API 804 passed + 6 skips; web unit 89; lint/types clean.
- **Not done:** live Gemini (ISSUES #56/#13); e2e not re-run for this chunk; light theme of `/design` not looked at yet.

## 2026-11-25 · S10 · P3 landing page + demo requests (loop chunk 2)
- **Done:** public landing page at `/` (server-rendered; signed-in users go to the app; hero with a self-typing sample Analyst exchange, principles strip, problems, feature tour with sample visuals, how it works, trust and security, FAQ, demo form, footer; skip link; every visual labelled "Sample data"). Proxy: `/` and `/login` are the only public pages. Demo requests (decision D3): `lumiant.leads` store, Alembic `0002_demo_request`, `POST /api/public/demo-requests` (CSRF, IP rate limit, consent, honeypot, control-character stripping, no personal details in logs), `GET /api/admin/demo-requests` for `super_admin` only.
- **Bugs fixed:** hidden chart tables widened pages (sr-only on `<table>`); duplicated "could not be reached" sentence in the app shell; landing grid columns now shrink (`min-w-0`).
- **Commands + results:** TEST_RUNS S10-6…S10-8.
- **Not done:** admin screen listing demo requests (API only); sign-in page redesign; no email notification for new requests.

## 2026-11-25 · S10 · Owner feedback pass + agent bug hunt (loop chunk 3)
- **Owner:** "no em dash and no AI-ish colours". Removed every em dash from visible text: web UI copy (commas, colons, "·"), empty-value placeholder now "–", Analyst answer text and choice labels, synthetic warehouse names ("North Plant: Raw Materials Store"), dev-login notice, planning notes; S10 docs too. Removed the gold `--ai` tint and its classes, the page wash, the hero radial glow, sparkle badges in new pages and the purple series from the chart kit; AI work now uses neutral surfaces and the brand teal/navy. DEC-028.
- **Agent bug hunt:** a 16-question offline batch found three routing/wording bugs (TEST_RUNS S10-9), fixed with tests: "how many items" now gives the inventory summary; the definition fallback only fires on "what is / mean / explain / define" questions without codes or numbers; grouped answers read "X holds the most stock: N".
- **Commands + results:** TEST_RUNS S10-9…S10-12.

## 2026-11-25 · S10 · Overview treemap, sign-in, admin list (loop chunk 4)
- **Done:** `ValueBars` gains `variant="treemap"`; Overview shows value by item group as a treemap on real data (click → Analyst). Sign-in page is a split view: user list left, sticky product panel right (sample KPI labelled), link back to the landing page. Admin gains a "Demo requests" tab (platform administrators only). Definition answers no longer repeat their heading.
- **Commands + results:** TEST_RUNS S10-14, S10-15; e2e rerun pending at the time of writing (S10-16).

## 2026-11-25 · S10 · Premium palette and type pairing (loop chunk 5)
- **Owner:** "use premium UI/UX colour and font combination". Built "Navy & Brass" from the logo colours (DEC-029): ink-navy and warm ivory in dark with champagne actions; ivory paper with navy ink and actions in light; brass only for brand marks; chart grid lines warmed to match. Added Newsreader (variable serif, self-hosted from npm, SIL OFL) as `font-display` for page titles, landing headlines and the sign-in panel; Inter stays for UI and numbers.
- **Also fixed:** logo box on the landing header; regenerated local demo data so warehouse names carry no em dash.
- **Commands + results:** TEST_RUNS S10-17, S10-18; e2e S10-19 pending at the time of writing.
- **Known:** a visitor whose session cookie expired lands on sign-in rather than the landing page (the app clears the cookie on the 401); sign-in links back to the landing page.

## 2026-11-25 · S10 · Layout redesign (loop chunk 6)
- **Owner:** "full redesign … colours, design, layout fully premium". Shared building blocks changed so every screen follows (DEC-030): floating-canvas shell, logo tile, raised active nav pill, card-style user block, 10/16/16 px radii, panel and table padding 20–24 px, eyebrow KPI labels with 32 px figures, `space-y-8` page rhythm. No route, wording, permission or test id changed.
- **Checks:** typecheck, lint, unit 90 green; looked at Overview at 1440 px (light) while the owner was using the pane; e2e S10-20 was interrupted; rerun with chunk 7 (S10-24).

## 2026-11-26 · S10 · Dark theme fix (loop chunk 7)
- **Owner:** "the dark mode colours are not at all good, fix them and complete the work". Cause: blue navy planes made every panel, line and chart read cold and muddy against warm ivory text. Replaced with warm-neutral charcoal "Obsidian" (DEC-031); chart grid, axis and diverging midpoint follow; light theme unchanged.
- **Logo:** the dark logo file has a navy background baked in, so `BrandLogo` now draws a `--logo-plate` (navy in dark, white in light) by default: a deliberate brand tile in the sidebar, mobile header, sign-in and landing header/footer. `/design` lists `--canvas` and `--logo-plate`.
- **Docs:** FRONTEND.md, BRAND_IMPLEMENTATION.md, PRODUCT_V2_PLAN.md §3 updated.
- **Commands + results:** TEST_RUNS S10-20 (interrupted earlier run), S10-21…S10-24: contrast AA on every plane, typecheck/lint clean, unit 90, browser check dark and light, e2e 37/37.

## 2026-11-26 · S10 · Product v3 plan (proposed)
- **Owner:** "plan it so businesses can use it as a plugin or the best way to connect their database; improve UI/UX and all visuals; act as a senior engineer and find what can be improved".
- **Audit (verified in code):** only a DuckDB connector (`connectors/registry.py`, `tenancy/models.py:30`); tenants and mappings are YAML; no jobs or scheduler; scale limits in `analyses/risks.py` still present; open correctness bugs #44–#47, #49; Overview has no time series; live Gemini never run.
- **Wrote** `05-plan/PRODUCT_V3_PLAN.md`: three data doors (direct read-only SQL, ERP extract to snapshot, files; self-hosted now, gateway later), connector contract v2 with a container conformance suite, Connect wizard and Mapping Studio with approval and reconciliation, tenant config into the DB, secret store, worker; "plugin" surfaces on the same typed tools (public API, MCP server, webhooks, embeds, Teams/Slack, Excel); new screens and visuals; senior-engineer fix list; phases V0–V6; owner decisions E1–E8.
- **Not done:** nothing built; waiting for the owner's approval of E1–E8 and the start order.

## 2026-11-26 · S10 · V0 correctness and speed (PRODUCT_V3_PLAN, owner approved)
- **Bugs fixed (each with a regression test):** #44 Analyst kept dropping filters named in a question (grouping now from "by X", named values become filters, clarifying question when a value cannot be applied); #45 expiry counts lots as lots, with stock lines alongside; #46 Admin schema check lists warehouses in the data but not in the configuration (and stock rows without a warehouse id); #47 stale-data warning in the insight feed (banner) and in every answer with figures; #49 / LA-09 governed plans compile and pass the guard for DuckDB, PostgreSQL, SQL Server and Oracle (TOP without OFFSET, null ordering without NULLS LAST on T-SQL, `LOWER` allowed).
- **Scale:** ABC in SQL with window sums (no 1,000-item cap, matches the Python reference on full data); cost comparison and the item-code check read every row in pages; filter lists sorted, up to `max_rows`, with `truncated` flags and a UI note; the Overview's largest-group share uses the value total.
- **Speed:** shared result cache (`analyses/cache.py`, 60 s, scope + permissions + data timestamp; DEC-032); the KPI, area board and panel share one below-reorder request; Refresh on the insight feed really re-runs (`fresh=true`). Query budget test and an in-process Overview benchmark (`services/api/benchmarks/overview_load.py`); bundle report and CI budget (`apps/web/scripts/bundle-report.mjs`, `bundle-budget.json`).
- **Gates:** axe in e2e (light + dark, 12 screens, 0 serious/critical) found and fixed: unfocusable scroll regions (tables, timeline), the Refresh button's name not containing its visible text, red delta text on a red tint in dark (new `--status-critical-ink`); screenshot spec for landing, sign-in and `/design` in both themes (Windows baselines); CI uploads Playwright traces on failure. e2e ports configurable (`LUMIANT_E2E_WEB_PORT`) because another local project uses 3100.
- **How:** steps #44, #46 and #49 ran in three parallel sessions in this checkout; the rest here. **Commands + results:** TEST_RUNS S10-25 … S10-31.
- **Open:** ISSUES #57 (landing JS above budget), #58 (cache per process), #59 (data quality 16 queries), #60 (no Linux screenshot baselines), #61 (risk tools ignore a named warehouse).

## 2026-11-26 · S10 · V1 connect (part 1): SQL connector and Data source
- **Done:** generic read-only `SqlConnector` (PostgreSQL, SQL Server, MySQL, Oracle; SQLite as a dev stand-in) behind the same contract as DuckDB; tenant `connection: {type: sql, secret_ref: env:NAME}`; unset URL fails safe (503); `lumiant-synthetic copy` loads a generated warehouse into any engine; conformance suite (SQLite every run, PostgreSQL in CI); `POST /api/admin/source/test` probe (connect, privilege check, catalog) that never stores or echoes the URL; `GET /api/admin/source`; Admin › Data source tab (status, rows per dataset, test a connection).
- **Commands + results:** TEST_RUNS S10-32 … S10-34.
- **Not done (next):** encrypted credential store and saving a source from the UI, mapping studio (V2), sync jobs.

## 2026-11-26 · S10 · V2 map and trust: suggestions and validation
- **Done:** `mapping/suggest.py` suggests the table and columns for each canonical dataset from names only (SAP field names, common ERP names, canonical names, table-name hints with specific vs generic words, exact-name bonus for prepared views), with confidence, reasons, alternatives and a YAML draft; `admin/validation.py` checks key uniqueness, orphans and missing required values (counts only). API: `GET /api/admin/mapping/suggest` (second opinion on the mapping in force), `POST /api/admin/source/suggest` (for a URL, used once), `GET /api/admin/validation`. Admin gains Mapping and Validation tabs; the connection test offers "Suggest a mapping".
- **Approval** stays config-as-code (ADR-0006): the draft is reviewed and committed like code, then the schema check, validation and reconciliation gate go-live. A stored, versioned approval in the app needs the tenant config in the database (PRODUCT_V3_PLAN E3), still open.
- **Commands + results:** TEST_RUNS S10-35, S10-36.

## 2026-11-26 · S10 · V3 integrations and V4 value trend
- **V3:** API keys for service accounts (`apikeys/store.py`, Alembic 0003, Admin › Integrations: create once-shown keys, list, revoke); any read endpoint accepts `Bearer lmk_...`; MCP server at `POST /mcp` exposing the Analyst's typed tools plus `ask_lumiant` within the key's rights and scope (DEC-033, `06-operations/INTEGRATIONS.md`).
- **V4 (start):** `GET /api/analyses/value-trend`: month-end inventory value for 12 months rebuilt from signed movements at current prices, with monthly receipts and issues, summed in the source; Overview shows it above the insight feed.
- **Commands + results:** TEST_RUNS S10-37 … S10-39.

## 2026-11-26 · S10 · V4 Material 360
- **Done:** `GET /api/items/{item_id}` (master, stock by warehouse with value for cost roles, lots on hand, latest movements, reorder rules, purchase orders; each section a validated, scoped plan with provenance, unavailable sections say why); Inventory rows open a Material 360 side sheet (native modal dialog, Esc closes).
- **Commands + results:** TEST_RUNS S10-40.

## 2026-11-26 · S10 · ISSUES #61 and stock ageing
- **#61 fixed:** a single named warehouse narrows below-reorder, excess, dormant and expiry answers (scope-checked narrowing).
- **V4 visual:** `GET /api/analyses/ageing` (on-hand stock by days since last issue, pairs for everyone, value per currency for cost roles, one statement in the source); Risks page shows it above the tabs.
- **Commands + results:** TEST_RUNS S10-42, S10-43.

## 2026-11-26 · S10 · V5 Settings
- **Done:** `/settings` for every user (linked from the user card): theme Light / Dark / System, navigation Expanded / Compact, account (name, workspace, roles, warehouses), keyboard shortcuts. Browser-local preferences; nothing new on the server.
- **Commands + results:** TEST_RUNS S10-44.

## 2026-11-26 · S10 · V1 encrypted connection store
- **Done:** `connectors/secret_store.py` (Fernet under `LUMIANT_SECRET_KEY`, Alembic 0004), `secret_ref: store` for tenants, `POST /api/admin/source/save` (probe first, refuse writable accounts, connector cache and result cache reset), `GET /api/admin/source/saved`; Data source tab gains "Save this connection" and the saved status. `cryptography` is now a direct dependency (was already present through PyJWT). `.env.example` documents the key.
- **Commands + results:** TEST_RUNS S10-45.

## 2026-11-26 · S10 · V3 alert rules and signed webhooks
- **Done:** `alerts/service.py` + Alembic 0005: rules (name, https target, minimum severity) with an encrypted signing secret shown once; "Send now" computes the insight feed for the sender's scope and POSTs the matching findings with `X-Lumiant-Signature` (HMAC-SHA256) and a timestamp; SSRF guard (https only, no private, loopback, link-local or reserved addresses) in production; last delivery status kept. Admin › Integrations gains Alert rules. `06-operations/INTEGRATIONS.md` explains verification.
- **Not done:** scheduled sending (needs the V1 worker); today a rule sends on "Send now" or through the API.
- **Commands + results:** TEST_RUNS S10-46.

## 2026-11-26 · S10 · V5 first-run welcome
- **Done:** a dismissible "Getting started" card on the Overview (four areas, ask about anything with right-click or L, Ctrl K, how each number was calculated), remembered per browser. TEST_RUNS S10-47.

## 2026-11-26 · S10 · Scheduled alert rules
- **Done:** rules can repeat every hour, day or week (Alembic 0006 adds the interval and the creator's rights snapshot); `lumiant-alerts send-due` sends due rules with that snapshot (cron or Kubernetes CronJob); the alert form offers the schedule. No resident worker process needed. TEST_RUNS S10-49.

## 2026-11-26 · S10 · Saved views API (session ended at the usage limit)
- **Done:** `/api/views` (list, save, delete; per user, only the page's known query keys kept; Alembic 0007), `test_views.py` passes.
- **Not done:** the Inventory "Save view" UI; full API and e2e suites were not re-run after this last step.
