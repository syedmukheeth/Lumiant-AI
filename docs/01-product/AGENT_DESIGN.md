# Inventory Agent Design

Status: **Implemented (M3) on synthetic data.** Built-in matcher verified; the external-LLM adapter is tested only against a fake client (ISSUES #13). Not yet: editable query chips, tenant glossary, capability matrix, per-conversation memory (M5). Code: `services/api/src/lumiant/agent/`; evals: `services/api/evals/`.

## 1. Principle

> The LLM never writes SQL and never computes authoritative numbers.

The model has exactly two jobs: (a) choose a tool from a fixed catalog and fill its typed arguments, (b) phrase an answer around results the application returned. Authorization, scope, SQL, arithmetic and provenance are application code. This makes the agent's security independent of model behaviour (brief §10.3, §11).

## 2. Pipeline

```
question
  → auth (Principal: tenant, roles, permissions, warehouse scope)
  → context assembly: canonical catalog for this tenant (names, types, descriptions — NOT physical names),
                       capability matrix, tenant glossary, last turn's plan (for follow-ups)
  → agent loop (bounded: ≤ 4 tool calls, token + time budget)
       tool call ─► validator ─► compiler ─► sql_guard ─► connector ─► ResultSet + provenance
  → composer: answer text + table/chart spec + follow-ups + warnings (stale, truncated, missing data)
  → grounding guard: every number in prose must appear in tool results (or a declared derivation)
       fail → one regeneration → still fail → templated answer from structured results
  → chart spec validation (field exists in result, chart type fits data shape)
  → UI: answer, table/chart, provenance card, editable query chips, follow-ups, feedback
```

## 3. Tool catalog

| Tool | Kind | Purpose | Needs (capability) |
|---|---|---|---|
| `query_inventory(plan)` | generic | Exploratory aggregates/filters over approved canonical datasets | dataset mapped |
| `stock_position(item?, warehouse?)` | analysis | On-hand by item/warehouse/location/lot | stock_balance |
| `below_reorder(filters)` | analysis | Items under customer reorder level (incl. zero-stock with policy) | reorder_policy, stock_balance |
| `excess_stock(filters)` | analysis | Above customer max | reorder_policy.max_stock |
| `slow_moving(days, filters)` / `dormant` | analysis | No/low issues in period | inventory_transaction |
| `inventory_ageing(buckets)` | analysis | Age of on-hand stock | lot.receipt_date or FIFO layers |
| `expiring_lots(within_days)` | analysis | Lots near/past expiry | lot.expiry_date |
| `cost_comparison(items, methods)` | analysis | latest price vs moving avg vs FIFO layer vs lot cost | approved costing rules (Q-006–Q-008) |
| `fifo_pick(item, warehouse, qty)` | analysis | Oldest eligible lots to issue (operational) | lot receipt dates |
| `abc_compare(method, period)` | analysis | Computed ABC vs assigned | approved ABC method (Q-005) |
| `master_data_quality(checks)` | analysis | Missing policy/cost/UoM, invalid codes, duplicates | item, coding rules |
| `warehouse_comparison(a, b, measure)` | analysis | Side-by-side | stock_balance |
| `price_movement(item, period)` | analysis | Unusual purchase-price changes (configured threshold) | purchase_record |
| `storage_mismatch()` | analysis | Item storage needs vs location capabilities | both mapped, else disabled |
| `resolve_entity(text, kind)` | helper | Fuzzy item/warehouse/supplier lookup **within scope** | — |
| `data_availability(topic)` | helper | What is mapped, freshness, what's missing | — |

Every analysis declares `required_fields`; the capability matrix disables tools whose fields are not mapped and gives the agent the exact sentence to explain why (e.g. *"I cannot calculate ageing because receipt dates are not available in the mapped data."*).

## 4. Guardrails

| Risk | Control (code, not prompt) |
|---|---|
| Scope widening ("show all warehouses") | Validator injects `warehouse_id IN (scope)` *after* the plan; explicit out-of-scope filters → 403 |
| Sensitive fields (costs) | Fields tagged `sensitivity=cost`; stripped from the catalog shown to the model and rejected by validator without `cost:read` |
| Arbitrary SQL | No SQL tool exists; compiler builds SQL only from validated plans; sqlglot guard re-checks |
| Prompt injection in data | Retrieved text is passed as quoted data in tool results, never as instructions; model has no tools that can change permissions; planted injection rows in synthetic data + eval cases |
| Hallucinated numbers | Grounding guard; tables/charts rendered from structured results, not from prose |
| Cross-tenant | Tenant only from token; per-tenant connector; catalog/glossary loaded per tenant |
| Runaway cost | Tool-call cap, token budget, per-tenant rate limits (M6), result row caps |
| Stale data | As-of from freshness metadata; warning above configured staleness threshold |

## 5. AI data boundary (what leaves the system)

Sent to the model: user question; canonical dataset/field names and descriptions permitted for this user; tool results capped (e.g. ≤ 50 rows, aggregated preferred); tenant glossary; up to 300 characters of each earlier answer (S11). Sent for embeddings (knowledge search, DEC-038): product text, the question, and the approved tenant's catalog text (mapped canonical fields, attribute descriptions, source hints; cost fields only for roles with cost access).
Never sent: credentials, physical table names, SQL, rows beyond the cap, fields the user cannot see, other tenants' anything.
Per request, a **disclosure log** records exactly what was sent (viewable by tenant admins; retention configurable). External providers require customer approval (Q-013); **AI-off mode** keeps the product usable without any LLM.

## 6. Provider abstraction

`LLMProvider` interface: `complete(messages, tools, tool_choice, max_tokens, timeout) -> ToolCalls | Text`, with adapters for Anthropic API, AWS Bedrock, Google Vertex, Azure OpenAI, and OpenAI-compatible self-hosted endpoints. Model ids are configuration. Before writing any LLM code, consult the `claude-api` skill for current model ids, tool-use format and caching.

## 6a. Providers in this repository (ADR-0009)

`rules` (built-in matcher, default, offline), `anthropic` and `gemini` (`GeminiProvider`, `google-genai`, automatic function calling off). External providers need the tenant's `ai.external_provider_approved` and a key; any failure falls back to `rules`. Both see the screen context as validated ids only.

## 6b. Screen context, follow-ups, streaming and insights (ADR-0010)

- **Context**: optional `context` {page, widget, filters, ≤ 5 selections of kind warehouse / location / item / item_group / stage / abc / stock_status / metric / insight}. Warehouses and items are checked against the principal before any tool runs; filters only narrow (`warehouse_id`, `location_id`, `item_group`, `stage`, `stock_status` on `stock_by`, `top_value_items`, `concentration`); `only` on `stock_by` compares 2–5 chosen values. Labels never reach tools, evidence or models.
- **Vague questions about selections** ("why is this high?", "compare these") route by selection kind in the matcher; **follow-ups** ("what about quantity?", "and by item group?") re-run the previous tool with the change, using `history` (questions + tools + arguments only).
- **Streaming**: `POST /api/agent/chat/stream` (SSE) sends `step` events (understand → each tool with row count and time → compose → grounding), `block` events, then the same `answer` as `/chat` (which now also returns `steps` and `elapsed_ms`).
- **New tools**: `concentration` (Pareto per currency: items holding the target share, top-10 share, capped honestly at the row limit) and `insights` (the insight feed). 12 tools in total.
- **Insight feed** `GET /api/insights`: deterministic rules over the analyses; gaps name the customer data that would unlock a rule.

## 7. Conversation features

- **Clarification**: ambiguous entity → choices (scope-filtered) instead of guessing.
- **Follow-ups modify the previous plan** ("now only North Plant") → implemented in the matcher for measure, grouping, warehouse and day window (§6b); a plan diff shown as chips is not built yet.
- **Editable query chips**: users change filters/grouping directly → deterministic re-run, no LLM call.
- **Feedback**: thumbs + reason → admin review → promotable to the golden eval set.

## 8. Evaluation harness

- `evals/golden/*.yaml`: question → expected tool + plan (or analysis args) → expected key numbers on synthetic data.
- `evals/adversarial/*.yaml`: prompt injection via data, cross-tenant requests, cost probing for no-cost users, out-of-scope warehouses, DML requests, "ignore previous instructions", oversized requests.
- Metrics: plan exact-match / semantic match, refusal correctness, grounding pass rate, latency, tokens.
- Runs in CI with recorded model responses; live-model runs on demand.

## 9. Supported question set (initial, M3)

1. Stock of item X (by warehouse). 2. Warehouse with most stock value. 3. Category-A items below reorder. 4. Spare parts not moved in N months. 5. Latest price of item X (per approved definition). 6. Latest price vs average cost. 7. Inventory by warehouse and item group. 8. Lots nearing expiry. 9. Items with incomplete master data. 10. Compare inventory value of two warehouses. 11. Highest-value items. 12. Items requiring special storage.
"Which items may become obsolete?" is answered honestly as *not supported without lifecycle data* (REQ-061), offering dormant/slow-moving instead.

## 10. Business questions, derived figures and the AI allowance (S11, ADR-0013)
- **Inventory levers.** Goal questions ("make 200000 profit", "free up cash", "cut carrying cost") call
  `inventory_levers`. It sizes stock above maximum, stock not issued in 270 days, expired lots and lots expiring
  within 90 days, with their value per currency (cost access only). It also counts pairs below reorder level, pairs
  without a policy and stock lines without a valuation price. Each lever comes with an action and a "not in your
  data" line (no sales history, selling prices or margins, so no profit figure). The built-in matcher routes these
  questions too, so the answer works without external AI.
- **`calculate`.** The model asks the application for a sum, difference, ratio, % change or share. It cites result
  cells by reference (`c<call>.r<row>.<field>`, shown as `ref` on every row it sees), or a number already in the
  results or the question. Decimal arithmetic; units and currencies must agree; the result is evidence. The model
  still never writes a figure itself.
- **More analyses as tools:** `stock_ageing`, `value_trend` (line chart block, cost access), `computed_abc` (cutoffs
  required, no defaults) and `open_purchase_orders` (scoped, overdue count).
- **Answer format (Gemini).** One direct sentence; up to five findings with figures; up to three actions; a "Not in
  your data:" line when something is missing; at most about 150 words, in the user's language.
- **History.** Each earlier turn may carry the first 300 characters of its answer, as context only. Evidence comes
  from this question's results alone.
- **Evidence.** Timings, request ids and SQL are not evidence (LA-10).
- **Cost guard (DEC-037).** Each external model call spends one unit of the tenant's rolling 24-hour allowance
  (`LUMIANT_AI_DAILY_CALLS`, default 300); when it is spent, the built-in matcher answers with a notice. There is a
  45 s deadline per question. Live evaluation: `services/api/eval/analyst_live.py` runs the 42 cases in
  `services/api/evals/live.yaml`.
