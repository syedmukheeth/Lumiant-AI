# Implementation Plan (checkbox tracker)

Tick an item **only when it is verified** (a test or recorded check). Link evidence in `logs/WORKLOG.md`.
Order follows dependencies. Milestone detail: `ROADMAP.md`, `MILESTONE_01.md`.

## Phase 1 — Investigation & design (brief Phases 1–3)
- [x] Inspect working directory, git status, toolchain (S01)
- [x] Check current package versions on npm/PyPI (S01)
- [x] Project assessment A–J (`00-context/PROJECT_ASSESSMENT.md`)
- [x] Requirements, open questions, architecture, security plan, roadmap
- [x] Knowledge base + logging protocol

## M1 — Foundation
### Step 1 — repo + knowledge base
- [x] `git init` (no commits until the owner asks)
- [x] Knowledge base written (`docs/`)
- [x] `CLAUDE.md`, `AGENTS.md`, `.gitignore`, `.editorconfig`, `.gitattributes` (root `README.md` written at step 8)
### Step 2 — dependency spike
- [x] DuckDB 1.5 + duckdb-engine + SQLAlchemy 2.0: compile, bound params, read_only, interrupt
- [x] Record result in ADR-0005
### Step 3 — API core
- [x] `pyproject.toml`, uv lock, ruff/mypy/pytest config
- [x] Settings + env validation (dev auth refused in production)
- [x] JSON logging, request context, error model (exercised by API tests in step 6)
- [x] Tenant config models + registry + 2 demo tenant YAMLs
- [x] Canonical catalog
- [x] Mapping resolver
### Step 4 — synthetic data
- [x] Generator (deterministic) + scenarios
- [x] Writer using tenant mapping → DuckDB
- [x] CLI `lumiant-synthetic`
- [x] Tests: determinism, balances = Σ txns, no negative lots, scenarios present
### Step 5 — query core
- [x] Connector protocol + DuckDB connector (read-only, timeout, row cap)
- [x] QueryPlan + validator (incl. scope injection, safety rails)
- [x] Compiler + sql_guard + executor + provenance
- [x] Audit store (SQLite + Alembic)
### Step 6 — auth, RBAC, routes
- [x] Dev auth provider, principal, permission deps
- [x] Routes: health, auth, meta, metrics, inventory, below-reorder, query
- [x] Metric catalog
- [x] Integration tests (independent raw SQL)
- [x] Security tests
### Step 7 — web
- [x] Next.js scaffold (TS 5.9, Tailwind 4, lint, vitest, playwright)
- [x] API client + formatters
- [x] Login, shell, overview, inventory
- [x] Vitest + Playwright
### Step 8 — close
- [x] Full check run recorded in TEST_RUNS
- [x] Browser check (desktop + mobile width)
- [x] Docs synced; CURRENT_STATE rewritten; ACCEPTANCE_CRITERIA updated

## M2 — Intelligence engine (next; detailed when started)
- [x] Hand-verified financial fixtures (zero qty, negative stock, duplicates, returns, mixed currency/UoM, period boundaries, rounding)
- [x] Moving weighted average engine + reconciliation against the source valuation price
- [x] Periodic weighted average, FIFO cost layers, lot cost, latest-price definitions (draft)
- [x] Computed vs assigned ABC (caller-supplied cutoffs; period/value definition fixed to on-hand value as a draft)
- [x] Analyses: excess, dormant, expiring lots, master-data quality (ageing and price movement deferred)
- [x] Item-code parser per tenant
- [ ] Value maps in tenant mapping (ISSUES #3) — moved to M5

## M3 — AI agent (done on synthetic data; external provider unverified)
- [x] Tool catalog with typed args and permission filtering
- [x] Provider abstraction: built-in matcher + Anthropic adapter (fake-client tested only)
- [x] Bounded loop, grounding guard, template fallback
- [x] Clarification choices, honest unsupported answers
- [x] Disclosure log, feedback, audit
- [x] Golden + adversarial eval sets in CI tests
- [x] Chat UI
- [ ] Editable query chips, tenant glossary, capability matrix (moved to M5)

## M4 — Reports and guided menu (done on synthetic data)
- [x] Report definitions + metadata header
- [x] CSV and XLSX export with backend permission, audit, formula-injection protection
- [x] Printable view
- [x] Guided menu using the same services
- [ ] Drill-through, saved views, background generation (moved to M5/M6)

## M5 — Admin and onboarding (partly done)
- [x] Schema discovery and drift detection (metadata only)
- [x] Capability readiness matrix
- [x] Reconciliation harness with go-live verdict
- [x] Audit explorer
- [x] Value maps (M8: `datasets.<ds>.value_maps`, compiled to CASE, unmapped codes reported — ISSUES #3)
- [ ] Mapping editor + approval workflow, AI-suggested mappings, profiling, drill-through, saved views, query chips, glossary (ISSUES #15)

## M6 — Hardening and deployment preparation (done where possible without the customer)
- [x] Rate limiting
- [x] OIDC provider (tested with local keys only)
- [x] CSP
- [x] Dockerfiles, compose, CI workflow (unverified)
- [x] Production-readiness checklist, deployment guide, runbook, user/admin guides
- [ ] Verify containers, CI, PostgreSQL, real IdP, shared rate-limit store, nonce CSP, load test, pen-test, secret scanning, OpenTelemetry

## M7 — Customer integration (blocked)
See `ROADMAP.md` and `07-customer/OPEN_QUESTIONS.md`.

## M8 — Client SAP data intake (plan Part B; real files local-only, ADR-0008)
- [x] B1 Private-data guardrails: `var/private/` + explicit `.gitignore` lines, `test_private_data_guard.py`, owner authorization in the session log
- [x] B2 Importer `ingest/sap_exports.py` + `lumiant-ingest sap`: header contract, codes as text, exact decimals, total rows → control-total gate, manifest, atomic DuckDB, generated tenant YAML
- [x] B3 Platform: `customer_extract` classification (dev-only, flag, production refusal, badge, CONFIDENTIAL exports, external AI off), private tenant dir, `stock_status` / `source_value` / `item_warehouse`, value maps, mapped-fields-only explorer/reports/metrics, SAP data-quality checks, capability `needs_file`
- [x] B4 Synthetic twin `demo-gamma` (XLSX in client layout → same importer)
- [x] B5 Tests (importer edge cases, twin totals vs the XLSX files, DQ counts, classification guards, gitignore, balances without lots)
- [x] B6 Docs (`07-customer/CLIENT_DATA_INTAKE.md`, ADR-0008, Q-019…Q-026)
- [x] Real import run locally; gate passed; `git status` clean of private files (session log S03)
- [ ] Client answers Q-019…Q-026; next files (MB51/MSEG, MARC, MCHB/MCH1, T001W/T001L, EKPO)

## M9 — Agent: Gemini, screen context, streaming, insights (plan Part C)
- [x] C1 `GeminiProvider` (`google-genai`, automatic function calling off, fake-client tests), settings, tenant approval gate (ADR-0009)
- [x] C2 Screen context + history on `/api/agent/chat` (validated, narrowing only), contextual routing and follow-ups in the matcher, `only` comparisons, new tools `concentration` and `insights`
- [x] C3 `POST /api/agent/chat/stream` (SSE steps → blocks → answer)
- [x] C4 Insight engine + `GET /api/insights` (capability gaps name the missing customer data)
- [x] C5 Tests + evals (`test_agent_context.py`, 8 new golden/adversarial cases)
- [ ] Live check of the Gemini adapter with an owner key on a synthetic tenant (ISSUES #13)

## M10 — Premium "Command Center" UI (plan Part D)
- [x] D1 Design system: dark-first tokens, elevation + glass, validated data-viz palette, self-hosted fonts, motion constants + reduced motion, ISSUES #10
- [x] D2 Shell: icon rail + command bar, ⌘K palette (pages, materials, ask), shortcuts, route transitions, restyled shared primitives
- [x] D3 Analyst Lens: analyzable KPIs/panels/bars/rows/insights, Lens mode, persistent dock with streamed trace, pins (ADR-0010)
- [x] D4 (part) Overview as command center with the insight feed; assistant page on the shared streamed renderer
- [ ] D4 (rest) Inventory virtualized grid + Material 360 sheet; Risks/Costs/Reports/Admin restyle; Admin › Data sources
- [x] D5 (part) Vitest for SSE/selections/Lens; e2e for insights → Analyst, Lens compare, viewer leak check
- [ ] D5 (rest) axe accessibility run
- [x] D6 Docs (USER_GUIDE, FRONTEND § Analyst Lens, AGENT_DESIGN §6a/6b, ADR-0009/0010)
