# Current State

_Rewritten at the end of every session. Last update: 2026-11-27, S11 (form-control focus and disabled-button fixes,
Lumiant favicon, functions moved to `bom1`, plan docs corrected; PR #9 and #10 merged to `main`). S10 before it:
Product v2 P1–P3, redesign and Obsidian dark theme, Product v3 V0 done and V1–V5 partly done (PR #8)._

## Milestone
M1–M11 as before (synthetic data; client SAP extract local only). **Product v2** (PRODUCT_V2_PLAN): design system v2,
chart kit, Analyst v2 (multi-step Gemini loop, knowledge retrieval, fake-client tested), landing page, sign-in split
view, demo requests, premium layout redesign, "Obsidian" dark theme. **Product v3** (PRODUCT_V3_PLAN, owner approved):
V0 correctness and speed **done** (DEC-032); V1 connect, V2 map and trust, V3 use anywhere, V4 command centre
**partly done** (see the plan's phase table).
**Branch:** only `main` (feature branch merged and deleted, owner instruction). **Deployment:** Vercel project
`lumiant-ai` (Vercel Services: web + API, functions in `bom1` since S11, DEC-035), production builds from `main` at https://lumiant-ai.vercel.app. It is
public with development sign-in on synthetic data; Deployment Protection is off (owner decision). App DB is SQLite in
/tmp (temporary per instance).

## What works (verified by automated tests and browser checks)

| Capability | Evidence |
|---|---|
| Everything in the M1–M11 table of the previous state (query engine, scope, auth, analyses, agent, M8 extract, M10/M11 UI) | API suite, e2e |
| V0: five wrong-figure bugs fixed (#44–#47, #49); ABC in SQL with no item cap; paged analyses; filter truncation flags; shared scoped result cache; Overview 79 → 41 source queries | `test_scale_limits.py`, `test_overview_budget.py`, `test_dialect_matrix.py`, TEST_RUNS S10-25…S10-31 |
| V1: read-only `SqlConnector` for PostgreSQL / SQL Server / MySQL / Oracle (SQLite as dev stand-in), `connection: {type: sql, secret_ref}`, safe failure, `lumiant-synthetic copy`, Admin › Data source with a connection test; tested connections can be saved encrypted (`LUMIANT_SECRET_KEY`, `secret_ref: store`, DEC-034) | `test_sql_connector.py` (SQLite every run, PostgreSQL in CI), S10-32…S10-34 |
| V2: mapping suggestions from names (all four demo tenants matched exactly), validation harness (keys, orphans, required values), Admin › Mapping and Validation | `test_mapping_suggest.py`, S10-35 |
| V3: API keys (hashed, ⊆ creator), public API with keys, MCP server `POST /mcp` with the Analyst's typed tools + `ask_lumiant`, alert rules with signed webhooks and SSRF guard, Admin › Integrations | `test_api_keys_mcp.py`, DEC-033, `06-operations/INTEGRATIONS.md` |
| V4: 12-month value trend (rebuilt from movements, exact), Material 360 sheet from Inventory, stock ageing buckets on Risks; V5: Settings page; ISSUES #61 fixed | `test_trends.py`, `test_items.py`, `test_ageing.py`, e2e |
| Gates | API 953 passed + 15 env skips; web unit 90; e2e 55/55; PR #8 CI green on GitHub (axe in light and dark on 12 screens, Windows screenshot baselines); bundle budget in CI |

## What is simulated (not evidence of customer readiness)
- All demo data is synthetic; the client SAP extract is a local one-off.
- **External AI has never been called** (Gemini paths tested with fake clients; ISSUES #13, #56).
- PostgreSQL connector conformance runs only in CI; SQL Server, MySQL and Oracle compile and pass the guard but were
  never run against a real engine. No customer system has been connected.
- Authentication is development-only in practice (OIDC never ran against a real IdP).

## Not built yet
Tenant config in the database with versioned mapping
approval; sync worker and scheduled syncs (alerts already send on a schedule via `lumiant-alerts send-due`); embeds;
virtualised grid, more visuals, global filters, Analyst inline charts; first-run tour, SSO/SCIM, Helm chart; Teams/Slack/Excel.

## Known limitations
`../logs/ISSUES.md`: open include #13 (live AI), #16 (real IdP), #37 / #58 (per-process caches), #57 (landing JS above
budget, being reduced), #59 (data quality 16 queries), #60 (Windows-only screenshot baselines), plus the SAP-extract items #23–#30.

## Next step
1. Owner: keep the demo public or turn on Vercel Deployment Protection; a lasting deployment needs a managed
   PostgreSQL for the app DB and real sign-in.
2. Owner: paid Gemini key on a synthetic tenant for the first live AI check. Needs all three: `LUMIANT_AGENT_PROVIDER=gemini`,
   `LUMIANT_GEMINI_API_KEY` (Vercel env or `services/api/.env`), and `ai.external_provider_approved: true` on that tenant.
   As of S11 none is set. On the public demo anyone could spend the key: turn on protection or a budget first.
3. Continue V1 (secret store, config in DB, sync worker), V3 (webhooks, alerts), V4 (visuals, filters).
4. First customer: Q-001 (their database technology) decides which connector gets a real conformance run.

## How to run
`06-operations/DEV_SETUP.md`, `06-operations/TESTING.md`, `06-operations/INTEGRATIONS.md`. If ports 3000/3100 are taken
by another local project, the dev web server moves to 3001 and e2e takes `LUMIANT_E2E_WEB_PORT=3200`.
