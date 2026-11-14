# Implementation Progress

The central record of where development stands. Update it after every meaningful milestone.

| | |
|---|---|
| **Last updated** | 12 Nov 2026 |
| **Code base** | `origin/main` at `758153d` + uncommitted work on local branch `work/resume-phase-b` (nothing committed or pushed) |
| **Last completed phase** | **A — Baseline** and **B — Fix existing bugs** |
| **Current phase** | **C — Actual LLM integration**: code complete and fake-client tested; live verification blocked on an API key and tenant approval |
| **Next recommended action** | Owner supplies a provider key and approves external AI for a *synthetic* tenant, then run the live LLM checks in §6; in parallel start **D — connector framework** (a read-only SQLAlchemy connector behind the existing `Connector` protocol) |

---

## 1. How the state was recovered (12 Nov 2026)

- **Git:** HEAD was detached at `origin/main` `758153d` ("Docs: record green CI run"), with no merge, rebase or cherry-pick in progress. **No commits since the 11 Nov audit.** Uncommitted, kept as-is: `docs/CODEBASE_AUDIT.md`, `docs/ERP_INTEGRATION_ANALYSIS.md` (modified). Untracked, kept as-is: `apps/web/AGENTS.md`, `docs/06-operations/LOCAL_DEMO.md`, `docs/QUESTIONS_AND_LIMITATIONS.md`, `docs/PRODUCT_FUNCTIONALITY_AUDIT.md`, `docs/PRODUCT_DEMO_REFERENCE.md`, `reports/`, `research_notes/`. A local branch `work/resume-phase-b` was created at the same commit, so work is no longer on a detached HEAD. Nothing was discarded.
- **The A–F roadmap had not been started:** none of its documents existed and no code had changed since the audit. Of the named documents, only `docs/ENTERPRISE_DATA_ACCESS_AND_TRUST.md` exists. `AI_ASSISTANT_ARCHITECTURE`, `LLM_PROVIDER_CONFIGURATION`, `ERP_CONNECTOR_ARCHITECTURE`, `ODOO_INTEGRATION`, `SAP_INTEGRATION`, `ORACLE_FUSION_INTEGRATION`, `KNOWN_ISSUES_AND_FIXES` and `TESTING_GUIDE` do not; their topics are covered in `docs/02-architecture/`, `docs/06-operations/TESTING.md` and `docs/logs/ISSUES.md`.
- **Source of truth used:** the code, the tests, `docs/00-context/CURRENT_STATE.md`, and `docs/PRODUCT_FUNCTIONALITY_AUDIT.md` (11 Nov, verified by running the app).

---

## 2. Status

Statuses: **Completed and verified** · **Implemented but not verified** · **Partially implemented** · **Not implemented** · **Blocked by external dependency**.

| Task | Status | Evidence | Remaining work |
|---|---|---|---|
| Existing rule-based assistant | Completed and verified | `agent/providers.py` `RuleBasedProvider`; `tests/integration/test_agent.py` (golden + adversarial evals in `services/api/evals/`); 11 Nov audit run | Extended this session (§4) |
| Actual LLM integration | Implemented but not verified | `AnthropicProvider`, `GeminiProvider`, `build_provider` in `agent/providers.py`; tool choice + prose only, never SQL; fake-client tests `test_external_provider_*`, `test_ungrounded_model_prose_is_rejected`, `test_provider_failure_falls_back_to_rules` | **Blocked:** no provider key; `ai.external_provider_approved` is false on every tenant. Run §6 once both exist |
| Anthropic provider | Implemented but not verified | Messages API tool use, 2-turn compose with `tool_result`; default model `claude-opus-5-5` (`core/config.py` `agent_model`) | Live call with a key |
| Gemini provider | Implemented but not verified | `google-genai` client, automatic function calling disabled, default `gemini-flash-latest` | Live call with a key |
| Structured tool calling | Completed and verified | 13 typed tools in `agent/tools.py` `TOOLS` (Pydantic args, `extra="forbid"`); permission filter `tools_for`; `test_model_cannot_call_forbidden_or_malformed_tools` | — |
| Response verification | Completed and verified | `agent/grounding.py`; **this session:** a built-in sentence that fails the check is now withheld (`agent/service.py`), and display rounding to 2–3 decimals of a real result is accepted; `test_template_that_fails_grounding_is_withheld`, `test_grounding_accepts_display_rounding_only`, `test_data_quality_counts_are_grounded_on_every_tenant` | — |
| Conversation history | Completed and verified | `agent/context.py` `HistoryTurn` (no result data replayed); `tests/integration/test_agent_context.py`; audit API test ("what about quantity?", "and in warehouse 2100?") | — |
| English support | Completed and verified | Rule matching is English; evals | Wider phrasing coverage is better done by the LLM path |
| Arabic support | Not implemented | Rule matching has no Arabic patterns (audit: Arabic questions unsupported). The LLM path would accept Arabic, but that is unverified | Needs a live LLM (§6) or Arabic rule patterns; Arabic answer templates and RTL rendering not designed |
| Currency formatting | Completed and verified | **This session:** `_amount`, `_quantity`, `_money` in `agent/tools.py` — sentences show "USD 1,128,850.12" instead of "USD 1128850.11776790"; tables keep exact values; `test_answer_sentences_show_formatted_money` | — |
| Warehouse filtering | Completed and verified | Scope injection in `query/validator.py` (audit). **This session:** "Compare warehouses 1100 and 2100" returns only those (`RuleBasedProvider._warehouses`); `test_compare_named_warehouses_returns_only_those` | — |
| Demo Gamma dashboard bug | Completed and verified | **This session:** `ErrorState` shows a 409 data gap as "Needs more data" without an error reference (`components/data/widget.tsx`), on the KPI card and the Risks tabs; unit test `guards.test.tsx`; e2e "a tenant without reorder data shows a data gap" | — |
| Costs dropdown bug | Completed and verified | **This session:** `components/costs/costs-page.tsx` shows "GM01" instead of "GM01 ·" when a warehouse has no name | — |
| RBAC direct URL protection | Completed and verified | Server: every route checks permissions (unchanged). **This session:** `AppShell` doesn't mount a page outside the role's sections and shows "Not available for your role." (`components/shell/app-shell.tsx`, `nav.ts` `sectionFor`); e2e "direct URL: … requests nothing" asserts no `/api/analyses` or `/api/inventory/filters` calls | — |
| Stale Analyst selection chip | Completed and verified | **This session:** area "Ask next" chips clear earlier selections (`components/overview/area-board.tsx`); e2e "an area question clears an earlier Analyst selection" | Other general-question entry points (insight **Analyze**) intentionally keep their own selection |
| Development badge over "Sign out" | Completed and verified | **This session:** `devIndicators: false` in `apps/web/next.config.ts` (dev only; Next's error overlay still appears on errors) | — |
| ERP connector framework | Partially implemented | `connectors/base.py` `Connector` protocol; `connectors/registry.py` accepts only `duckdb` (others raise `NotImplementedError`); prototype `nomap/source.py` reads any SQLAlchemy URL read-only (not wired into the product) | Phase D: a read-only SQLAlchemy connector, credential handling via secret references, connection tests, metadata discovery behind the protocol |
| Odoo integration | Partially implemented | Prototype only: `nomap` evaluated against a real local Odoo 18 demo (`services/api/eval/nomap/odoo/`); no product connector | Product connector + mapping for Odoo's PostgreSQL schema, or decide to adopt `nomap` (reverses ADR-0002, owner's call) |
| SAP integration | Partially implemented | SAP list-export importer `ingest/sap_exports.py` (local, `customer_extract`); SAP-style tenants; SAP knowledge pack in `nomap/packs.py` | **Blocked:** a licensed, SAP-approved extraction route, legal review of SAP's API policy, and a sandbox system |
| Oracle Fusion integration | Blocked by external dependency | Nothing implemented | A BICC/BI Publisher export or a test pod; then a file connector + mapping |
| Schema discovery | Partially implemented | Admin › Connection and schema (`admin/service.py`) compares mapping with the live source (metadata only); `nomap/discovery.py` prototype discovers any schema | Bring discovery behind the connector protocol (Phase D) |
| Enterprise data privacy | Completed and verified (for what exists) | External AI requires configuration **and** tenant approval (`build_provider`); disclosure audited (`agent:disclosure`); model sees ≤ 20 rows, fields truncated (`model_view`); `customer_extract` tenants refuse external AI and production mode; tests `test_external_ai_requires_tenant_approval_and_key`, `test_disclosure_is_logged_*`, `test_private_data_guard.py` | Re-check once a live provider is enabled |
| Automated regression tests | Completed and verified | API and web suites (§5); this session added 8 API tests + 7 routing eval cases, 4 web unit tests and 3 e2e tests | — |

---

## 3. Roadmap vs current state

| Phase | Item | State |
|---|---|---|
| **A** Baseline | Inspect architecture · backend tests · frontend tests · baseline build · protect work | **Done** 12 Nov: API 465 passed / 6 skipped, ruff + mypy clean; web lint/tsc clean, 74 unit; work kept on branch `work/resume-phase-b` |
| **B** Fix bugs | Incorrect assistant intent | **Done** — 7 phrasings fixed (§4) |
| | Incorrect warehouse filtering | **Done** |
| | Failed numerical validation | **Done** — withheld, plus root cause fixed for data-quality counts |
| | Excessive decimal places | **Done** |
| | Conversation history | **Already worked** (verified in audit and tests); no change |
| | Stale Analyst selection chips | **Done** |
| | Demo Gamma dashboard | **Done** |
| | Demo Gamma Costs dropdown | **Done** |
| | Unauthorized direct URL access | **Done** |
| | Development badge overlapping sign-out | **Done** |
| **C** LLM | Real provider · structured tools · trusted engine · verification · unavailable provider · rule fallback · privacy | **Code complete and fake-client tested; live run blocked** (key + approval) |
| | Mode clearly identified | **Already present** ("Built-in matching" / "AI-assisted (Claude/Gemini)" under every answer, notice when AI isn't approved); withheld-answer wording fixed this session |
| | Arabic and English | English done; Arabic **not implemented** (needs live LLM or rules) |
| **D** Connectors | Interface · connection mgmt · discovery · canonical mapping · credentials · tests | Interface + canonical mapping + mapping checks exist; generic connector **not started** |
| **E** ERP | Odoo · SAP · Oracle Fusion | Prototype / importer only; real systems **blocked** (§2) |
| **F** Verification | Backend · frontend · production build · LLM · connectors · security · walkthrough | Backend, frontend, e2e (production build) run this session (§5); LLM and connector checks pending phases C/D |

---

## 4. Changes made this session (uncommitted)

**Assistant (API)**
- `services/api/src/lumiant/agent/providers.py` — new rules: total value / "how much inventory" → `inventory_summary` (only when no item is named); "highest inventory value" wording; "A-category / class B" items → `top_value_items` (or quantities for roles without cost) filtered by ABC class; "where is item X held" / "details of item X" → `stock_position`; "classifications" → breakdowns by ABC, item group and stage; "compare warehouses X and Y" → `stock_by` with `only`.
- `agent/tools.py` — new `inventory_summary` tool built on the Overview's catalog metrics; `abc_class` narrowing argument; formatted money and quantities in sentences (exact values stay in tables); data-quality counts added to the evidence.
- `agent/grounding.py` — accepts rounding to 2 or 3 decimals of a result value (nothing computed, no rounding to whole units).
- `agent/service.py` — a built-in sentence that fails grounding is withheld (tables kept); label for the new tool.
- `services/api/evals/golden.yaml`, `adversarial.yaml` — 7 new routing cases.
- `services/api/tests/integration/test_agent.py` — 8 new tests; the reorder test now expects the display form of the quantity (same strictness).

**Web**
- `apps/web/src/components/shell/app-shell.tsx`, `shell/nav.ts` — section guard for direct URLs.
- `components/data/widget.tsx` — 409 data gaps shown as "Needs more data".
- `components/costs/costs-page.tsx` — no dangling "·" for unnamed warehouses.
- `components/overview/area-board.tsx` — area questions clear earlier selections.
- `components/analyst/answer-view.tsx` — withheld-answer wording names AI only when AI answered.
- `apps/web/next.config.ts` — dev indicator off.
- Tests: `apps/web/tests/unit/guards.test.tsx` (new), 3 tests in `apps/web/e2e/app.spec.ts`.

**Docs**
- `docs/IMPLEMENTATION_PROGRESS.md` (this file).
- Not done: the repository's own logging protocol (WORKLOG, TEST_RUNS, CURRENT_STATE). Update those when this work is committed.

---

## 5. Tests performed (12 Nov 2026, Windows, local)

| Check | Result |
|---|---|
| Baseline API `pytest` (before edits) | 465 passed, 6 skipped (Redis-gated); ruff clean; mypy clean (87 files) |
| Baseline web | lint clean, tsc clean, 74 unit passed |
| Assistant tests after edits (`test_agent.py`, `test_agent_context.py`) | 86 passed (first run: 1 failure caught a routing conflict — "how much stock … for item X" — fixed) |
| ruff check, ruff format, mypy after edits | clean |
| Web after edits | lint clean, tsc clean, **78 unit passed** (4 new) |
| Full API suite after edits | **480 passed, 6 skipped** (465 + 8 new tests + 7 new eval cases) |
| Full e2e (production build, `pnpm e2e`) after edits | **29 passed** (26 + 3 new), 3.9 min |
| Web after the last edit (withheld-answer wording) | lint clean, tsc clean, 78 unit passed. The e2e build may predate this text-only change |

**Not run:** live LLM calls (blocked), PostgreSQL/Redis CI jobs and Docker (they run in GitHub Actions on push), a manual walkthrough in the browser pane. `uv` isn't installed on this machine, so the e2e web-server commands ran through a temporary stand-in outside the repo that calls the project's own `.venv` executables.

---

## 6. Blockers and how to clear them

| Blocker | Unblocks | Who |
|---|---|---|
| A paid Anthropic or Gemini API key in `services/api/.env` (`LUMIANT_AGENT_PROVIDER`, `LUMIANT_ANTHROPIC_API_KEY` / `LUMIANT_GEMINI_API_KEY`) | Live LLM verification, Arabic via the LLM | Owner |
| `ai.external_provider_approved: true` on a **synthetic** tenant only | Same | Owner (never on a customer tenant without the customer's written approval, Q-013) |
| Customer/partner sandbox credentials (Odoo, SAP, Oracle Fusion) | Phase E real-system tests | Customer / owner |
| SAP API-policy legal review | Any SAP connection beyond file exports | Owner / legal |
| Decision on ADR-0002 vs the `nomap` prototype | Whether schema discovery + AI-written SQL enters the product | Owner |

**Live LLM check, once unblocked:** ask the 14 questions in `docs/PRODUCT_DEMO_REFERENCE.md` plus the 7 new phrasings and 3 Arabic questions on demo-alpha; confirm `mode` is `anthropic`/`gemini`, every answer passes grounding, `agent:disclosure` audit rows appear, and a role without cost access never receives values.
