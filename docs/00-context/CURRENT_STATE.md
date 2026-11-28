# Current State

_Rewritten at the end of every session. Last update: 2026-11-28, S11.
- **Speed work** (ADR-0014, DEC-039), merged to `main` (PR #13, `ab9c6d4`) and live. On production, a rail click
  shows its page in under 100 ms (was 271 ms), TEST_RUNS S11-27. It covers:
  - client navigation cache and full prefetch around the nonce CSP
  - data prefetch on intent, and the session kept for reloads
  - filters without a server trip
  - a lighter, calmer shell
  - wider shared API results, and cold-start trims
- **Smart Analyst** (ADR-0013, DEC-036…038): inventory levers, app-computed figures, more analysis tools, time
  bucketing, RAG v2, chart answers, daily AI allowance; external AI approved on the four synthetic demos.
- **Earlier in S11:** form-control and favicon fixes; functions moved to `bom1` (PR #9, #10).
- **S10 before it:** Product v2 and Product v3 V0–V5 in part (PR #8)._

## Milestone
- **M1–M11:** as before (synthetic data; client SAP extract local only).
- **Product v2** (PRODUCT_V2_PLAN): design system v2, chart kit, Analyst v2, landing page and sign-in, "Obsidian"
  dark theme.
- **Product v3** (PRODUCT_V3_PLAN):
  - V0 done.
  - V1–V5 partly done (see the plan's phase table).
  - S11 adds the Smart Analyst. It covers V4 "Analyst inline charts", plus the trends that the query engine's time
    bucketing makes possible.
- **Branch:** only `main`.
- **Deployment:** Vercel project `lumiant-ai`.
  - Vercel Services: web + API, functions in `bom1` (DEC-035). Production builds from `main` at
    https://lumiant-ai.vercel.app.
  - Public, with development sign-in on synthetic data; Deployment Protection is off (owner decision).
  - App DB is SQLite in /tmp (temporary per instance).

## What works (verified by automated tests and browser checks)

| Capability | Evidence |
|---|---|
| Everything in the M1–M11 table of the earlier states (query engine, scope, auth, analyses, agent, M8 extract, M10/M11 UI) | API suite, e2e |
| V0–V4 items listed in S10 (correctness fixes, SQL connector and encrypted store, mapping suggestions, API keys, MCP, signed alerts, value trend, Material 360, ageing, Settings) | S10 TEST_RUNS |
| **Business questions:** `inventory_levers`. Values per currency, cost access only. It says what the data cannot show (no sales, prices or margins, so no profit figure). The built-in matcher routes goal questions (including misspellings and Arabic), so this works without any AI key | `test_agent_s11.py`, golden cases, TEST_RUNS S11-12 |
| **App-computed figures:** `calculate` (cell references, Decimal, mixed currencies refused); evidence excludes run metadata (LA-10) | `test_agent_s11.py`, ADR-0013 |
| **New tools:** `stock_ageing`, `value_trend` (line chart), `computed_abc` (cutoffs required), `open_purchase_orders`; every tool has a progress label | `test_agent_s11.py` |
| **Time bucketing:** `QueryPlan.time_bucket` (day, month, quarter, year) on all six dialects; `query_inventory` `period` with a chart block | `test_time_bucket.py`, `test_time_buckets.py` (sums equal a Python reference), dialect matrix |
| **RAG v2:** a per-tenant, per-role knowledge index; 20 new playbook and capability sections; a lasting vector cache (memory, committed file, app DB via Alembic 0008); `lumiant-knowledge embed`; retrieval eval (keyword recall@4 0.90 product, 0.95/0.94 tenant) | `test_knowledge_rag.py`, `test_retrieval_eval.py`, S11-13 |
| **Analyst UI:** chart blocks (line via the viz kit, bar), distinct unsupported and clarify layouts, styled notices; follow-ups carry the earlier answer (≤ 300 characters, context only) | web unit tests, S11-14 |
| **AI cost guard:** daily allowance per tenant (`LUMIANT_AI_DAILY_CALLS`, 300); 45 s deadline per question; Gemini output cap. A customer extract can never be AI-approved | `test_agent_s11.py`, `test_tenancy.py` |
| **Smooth navigation (ADR-0014, live):** rail routes prefetched in full and cached on the client, a route skeleton, data prefetched on link intent, session restored on reload, filters without a server trip, lazy palette, dock and charts, calmer motion. API: metrics, filters, ABC, cost comparison, concentration, the planning load and duplicates shared for 60 s (audited, scope-safe); SQLite `synchronous=NORMAL` | `navigation.spec.ts`, `session-cache.test.ts`, `test_result_cache.py`, TEST_RUNS S11-22 … S11-27 |
| **Gates** | API 1123 passed + 15 env skips; ruff and mypy clean; web unit 106; e2e: see TEST_RUNS S11-25; CI on PR #13 green (S11-27) |

## What is simulated (not evidence of customer readiness)
- All demo data is synthetic; the client SAP extract is a local one-off.
- **External AI has never been called.** Every Gemini path is tested with fake clients. The live harness
  (`services/api/eval/analyst_live.py`, 42 cases) is ready and waits for the owner's key (ISSUES #13, #56).
- **Connectors:** PostgreSQL conformance runs only in CI.
  - SQL Server and Oracle compile and pass the guard but were never run against a real engine.
  - **MySQL plans cannot pass the SQL guard at all** (`%s` placeholders, ISSUES #68), and MySQL ordering is invalid
    (#69).
  - No customer system has been connected.
- Authentication is development-only in practice (OIDC never ran against a real IdP).

## Not built yet
- Tenant config in the database with versioned mapping approval.
- Sync worker and scheduled syncs.
- Embeds.
- Tenant document upload for RAG (needs a managed Postgres).
- Multi-series period charts.
- Virtualised grid, global filters.
- SSO/SCIM, Helm chart.
- Teams, Slack and Excel apps.

## Known limitations
See `../logs/ISSUES.md`. Open items include:
- #13 / #56: live AI never run.
- #16: real IdP.
- #37 / #58: per-process caches.
- #57: landing JS above budget.
- #60: Windows-only screenshot baselines.
- #63: AI allowance per instance without Redis.
- #64: ageing and value trend have no provenance slip.
- #71: cold start after idle (narrowed; no keep-warm on the Hobby plan).
- #72: duplicates are cached but not paged on the server.
- #65: lever values are a floor beyond 200 rows.
- #66: retrieval eval ids depend on section order; no stemming.
- #67: knowledge vectors not precomputed.
- #68 / #69: MySQL guard and ordering.
- #70: period plus grouping draws no chart.
- The SAP-extract items #23–#30.

## Next step
0. **Cold start (#71):**
   1. Release the S11-29 fix (Overview requests start with the session). It is local and not committed yet; it
      needs a PR and the owner's go to merge.
   2. Still open:
      - the web function cold start (`/login` 4.6 s after idle)
      - the API starting one cold instance per parallel call on Vercel
      - no keep-warm on Hobby

      Trace with `node apps/web/scripts/sign-in-trace.mjs https://lumiant-ai.vercel.app` after an idle period.
1. **Owner:**
   1. Set a spending cap on the Gemini key in Google AI Studio.
   2. Add `LUMIANT_AGENT_PROVIDER=gemini` and `LUMIANT_GEMINI_API_KEY` in Vercel production and in
      `services/api/.env`.
   3. Then run `uv run python eval/analyst_live.py` and `uv run lumiant-knowledge embed`, and commit
      `content/vectors.json`.
   4. Consider Redis for a shared allowance, or Deployment Protection.
2. **Fix MySQL** (#68, #69) before any MySQL customer.
3. **Continue V1** (config in DB, sync worker) and **V4** (multi-series charts, filters, grid).
4. **First customer:** Q-001 (their database technology) decides which connector gets a real conformance run.

## How to run
- `06-operations/DEV_SETUP.md` (AI settings and allowance), `06-operations/TESTING.md`, `06-operations/INTEGRATIONS.md`.
- If ports 3000/3100 are taken by another local project, the dev web server moves to 3001 and e2e takes
  `LUMIANT_E2E_WEB_PORT=3200`.
