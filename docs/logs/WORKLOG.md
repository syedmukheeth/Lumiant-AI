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
