# ADR-0010: Contextual chat ("analyze anything"), streamed agent steps and a deterministic insight feed

- **Status:** Accepted
- **Date:** 2026-10-28
- **Session:** S04 (plan Parts C and D3)
- **Related:** ADR-0002, ADR-0009; `../../01-product/AGENT_DESIGN.md`; `../FRONTEND.md` § Analyst Lens

## Context
Users should be able to point at any KPI, bar, row or insight and ask about it, see the agent work instead of waiting, and get the important findings without asking.

## Decision
1. **Context is a hint, never an authority.** `ChatRequest` accepts an optional `context` (page, widget, filters, ≤ 5 selections of a fixed set of kinds) and `history` (≤ 6 turns of question + tool + arguments, no result data). All fields are typed, `extra="forbid"`, ids are printable and ≤ 64 characters. Before anything runs, selected/filtered warehouses must be visible to the principal and selected items must exist, else the answer is a refusal (audited `agent:context` deny). Context only pre-fills or **narrows** tool arguments (new optional filters on `stock_by` / `top_value_items` / `concentration`; `only` compares 2–5 chosen values); scope is still injected by the validator. Labels are display text: never used as filter values, never added to the grounding evidence, never sent to a model.
2. **Matcher routing for vague questions.** With selections present, "why/explain/this/compare" questions route by selection kind (a warehouse is explained by its item groups and top items, a group by its warehouses, a metric by its breakdown and value concentration, two selections are compared). Short follow-ups ("what about quantity?", "and by item group?") re-run the previous tool with the change; value is never granted to a role without cost access.
3. **Streaming.** `POST /api/agent/chat/stream` returns server-sent events: `step` (understand → each tool with row count and time → compose → grounding), `block`, then one `answer` identical to `/api/agent/chat` (which is kept). Same CSRF, rate limit and audit. Errors become an `error` event with a safe message.
4. **Insight feed.** `GET /api/insights` runs fixed rules over existing analyses (below reorder, expiring lots, stock tied up in QI/blocked/other statuses, excess, dormant, value concentration, location concentration, data quality). Each card has a severity, a template title with numbers from the results, metrics, provenance where available, a link and a seed question. Rules whose data is not mapped become **gaps** naming the customer data that would unlock them (e.g. MB51 movements); rules needing cost access are skipped for roles without it. Feeds are cached 120 s per tenant + scope + permissions; each figure is still produced by scope-injected queries. The agent exposes the same feed as the `insights` tool, and `concentration` as a tool.

## Consequences
Any element on screen can be analysed without typing ids; answers stay deterministic and grounded; perceived latency drops because steps and tables arrive as they finish. The insight feed works on the client extract today (statuses, concentration, data quality) and says what further SAP data would add.

## Alternatives considered
Sending the whole screen (rendered values) to the agent — would let browser-supplied numbers into answers. LLM-written insights — conflicts with ADR-0002. WebSockets — SSE is one-way, works through the Next.js rewrite and needs no extra infrastructure.

## Revisit when
Per-conversation memory is stored server-side; insight rules become tenant-configurable; a shared cache is needed across API replicas.
