# Current State

_Rewritten at the end of every session. Last update: 2026-11-26, S10 (Product v2 P1–P3, redesign and Obsidian dark
theme, Product v3 V0 done and V1–V4 partly done; all on `feature/product-v2`, pushed; `main` not changed)._

## Milestone
M1–M11 as before (synthetic data; client SAP extract local only). **Product v2** (PRODUCT_V2_PLAN): design system v2,
chart kit, Analyst v2 (multi-step Gemini loop, knowledge retrieval, fake-client tested), landing page, sign-in split
view, demo requests, premium layout redesign, "Obsidian" dark theme. **Product v3** (PRODUCT_V3_PLAN, owner approved):
V0 correctness and speed **done** (DEC-032); V1 connect, V2 map and trust, V3 use anywhere, V4 command centre
**partly done** (see the plan's phase table).
**Branch:** `feature/product-v2` (pushed). Merging to `main` and any deployment need the owner.

## What works (verified by automated tests and browser checks)

| Capability | Evidence |
|---|---|
| Everything in the M1–M11 table of the previous state (query engine, scope, auth, analyses, agent, M8 extract, M10/M11 UI) | API suite, e2e |
| V0: five wrong-figure bugs fixed (#44–#47, #49); ABC in SQL with no item cap; paged analyses; filter truncation flags; shared scoped result cache; Overview 79 → 41 source queries | `test_scale_limits.py`, `test_overview_budget.py`, `test_dialect_matrix.py`, TEST_RUNS S10-25…S10-31 |
| V1: read-only `SqlConnector` for PostgreSQL / SQL Server / MySQL / Oracle (SQLite as dev stand-in), `connection: {type: sql, secret_ref}`, safe failure, `lumiant-synthetic copy`, Admin › Data source with a connection test that never stores the URL | `test_sql_connector.py` (SQLite every run, PostgreSQL in CI), S10-32…S10-34 |
| V2: mapping suggestions from names (all four demo tenants matched exactly), validation harness (keys, orphans, required values), Admin › Mapping and Validation | `test_mapping_suggest.py`, S10-35 |
| V3: API keys (hashed, ⊆ creator), public API with keys, MCP server `POST /mcp` with the Analyst's typed tools + `ask_lumiant`, Admin › Integrations | `test_api_keys_mcp.py`, DEC-033, `06-operations/INTEGRATIONS.md` |
| V4: 12-month value trend (rebuilt from movements, exact), Material 360 sheet from Inventory | `test_trends.py`, `test_items.py`, e2e |
| Gates | API 930 passed + 15 env skips; web unit 90; e2e 50/50 (axe in light and dark on 12 screens, Windows screenshot baselines); bundle budget in CI |

## What is simulated (not evidence of customer readiness)
- All demo data is synthetic; the client SAP extract is a local one-off.
- **External AI has never been called** (Gemini paths tested with fake clients; ISSUES #13, #56).
- PostgreSQL connector conformance runs only in CI; SQL Server, MySQL and Oracle compile and pass the guard but were
  never run against a real engine. No customer system has been connected.
- Authentication is development-only in practice (OIDC never ran against a real IdP).

## Not built yet
Encrypted credential store and saving a source from the UI; tenant config in the database with versioned mapping
approval; sync worker and scheduler; webhooks, alert rules, embeds; virtualised grid, more visuals, global filters,
saved views, Analyst inline charts; settings page, first-run tour, SSO/SCIM, Helm chart; Teams/Slack/Excel.

## Known limitations
`../logs/ISSUES.md`: open include #13 (live AI), #16 (real IdP), #37 / #58 (per-process caches), #57 (landing JS above
budget, being reduced), #59 (data quality 16 queries), #60 (Windows-only screenshot baselines), #61 (risk tools ignore a
named warehouse), plus the SAP-extract items #23–#30.

## Next step
1. Owner reviews `feature/product-v2` and decides on merging to `main`.
2. Owner: paid Gemini key on a synthetic tenant for the first live AI check.
3. Continue V1 (secret store, config in DB, sync worker), V3 (webhooks, alerts), V4 (visuals, filters).
4. First customer: Q-001 (their database technology) decides which connector gets a real conformance run.

## How to run
`06-operations/DEV_SETUP.md`, `06-operations/TESTING.md`, `06-operations/INTEGRATIONS.md`. If ports 3000/3100 are taken
by another local project, the dev web server moves to 3001 and e2e takes `LUMIANT_E2E_WEB_PORT=3200`.
