# Product v2 Plan: from prototype to product

_Drafted 2026-11-25 (S10) at the owner's request: "next-level UI/UX, premium custom colours, far more visuals, a landing page, a fully working Gemini assistant with proper RAG, fast loads, a product, not a prototype." Status: **proposed, awaiting the owner's go-ahead.** Nothing in this file is built yet._

**Basis:** code at `956d4c0` (after PR #7), `UI_UX_AUDIT.md` (live review, findings UX-03…UX-20 still open), `UI_UX_IMPLEMENTATION_STATUS.md`, `agent/` and `query/` source. A fresh live look was attempted this session but the dev servers did not start in time on this machine (ISSUES #33 class), so this plan leans on the earlier live reviews.

---

## 1. Where we are, honestly

| Area | Today | Gap to "product" |
|---|---|---|
| First impression | `/` redirects straight to `/overview`; login is a plain form | No landing page, no story, no reason to trust us before sign-in |
| Visuals | Recharts used in **one** component (`value-bars.tsx`): horizontal bars. Everything else is KPI tiles and tables | No trends, no shape of the data: no Pareto, treemap, heatmap, timeline, sparkline, gauge |
| Overview | Inventory KPIs + insight feed + four bar panels | No executive view: fulfilment risk, shortages, procurement and supplier tiles are on other pages only |
| Inventory | Stock-line table; Value column was off-screen (fixed), no item page | No Material 360, no column chooser, single-value filters (UX-07, UX-08, UX-16) |
| Assistant | Strong safety (typed tools, grounding guard, scope checks, audit). Gemini adapter exists, **never called live** (ISSUES #13). Model picks tools **once** (`decide` → run → `compose`) | Cannot chain steps, cannot ask the query engine freely, no knowledge retrieval, no charts in answers |
| Speed | Dev server slow on this machine; no measured budgets for production | No performance budget, no virtualised tables, no prefetch strategy |
| Product shell | Dev-only sign-in, no onboarding, no settings, no alerts centre | Real sign-in, first-run tour, user settings, notification centre |

Strengths to keep: provenance on every number, role-aware hiding, honest gaps, ⌘K palette, Analyst Lens, the official brand palette (navy, gold, teal from the logos), 787 API tests and 36 e2e tests.

---

## 2. Principles (what "next level" means here)

1. **Show the shape, then the number.** Every screen opens with a visual that answers "is this good or bad?" in one second, then the exact figure, then the source.
2. **One click to the why.** Every chart mark, KPI and row opens the Analyst or a detail drawer. No dead ends.
3. **Premium = restraint + depth.** Fewer borders, more space, layered surfaces, one accent per screen, motion that explains change (counts, morphs), never decoration.
4. **Fast is a feature.** Budgets in §7 are acceptance criteria, not hopes.
5. **The AI is clever, the numbers are code.** The model plans and explains; every figure still comes from the deterministic engine and passes the grounding guard (ADR-0002 stays).
6. **Synthetic stays labelled.** The SYNTHETIC badge and flag survive every redesign, including the landing page demo.

---

## 3. Visual identity v2 ("Lumiant Night & Day")

Keep the official palette from the logos (DEC in `BRAND_IMPLEMENTATION.md`); elevate how it is used.

| Token group | Change |
|---|---|
| Surfaces | Navy planes gain a subtle vertical gradient on the page plane and a 1-px top highlight on raised cards (depth without glow) |
| Accent | Teal stays the working accent in dark, navy in light. **Gold** becomes the signature for AI: Analyst button, AI-written text marker, landing hero line |
| Data colours | Existing validated `--viz-*` set; add a sequential teal ramp (heatmaps, treemap) and a diverging teal↔amber ramp (variance, over/under) — validated with the dataviz checker for both themes |
| Type | Inter for UI and numbers (tabular), Geist Mono for codes; add a display size (40/48 px, tight tracking) for landing and KPI heroes |
| Motion | Number count-up on KPI load (respecting reduced motion), chart enter morphs, drawer and dock spring; existing `lib/motion.ts` constants extended, not replaced |
| Illustration | Line-art empty states and onboarding visuals in brand colours (SVG, < 4 KB each) |

Deliverable: `docs/UI_UX_DESIGN_SYSTEM.md` v2 + tokens in `globals.css` + a `/design` internal showcase page listing every component and chart in both themes (the "colour showcase" the owner asked for).

---

## 4. Chart kit (new `components/viz/`)

Built on Recharts (already installed) plus small hand-written SVG where Recharts is weak. Every chart: tokens only, keyboard focusable marks, a visually hidden data table, a "Source" provenance slip, and a click → Analyst Lens.

| Component | Used for |
|---|---|
| `Sparkline` + `DeltaChip` | KPI tiles: 12-period trend and change vs last period |
| `TrendArea` | Inventory value / quantity over time, receipts vs issues |
| `ParetoChart` | ABC: cumulative value curve with A/B/C bands |
| `Treemap` | Value by item group → item (drill in place) |
| `HeatCalendar` | Expiry and receipts by day |
| `RiskMatrix` | Value × days-of-cover / days-dormant scatter with quadrant labels |
| `Gauge` / `RadialProgress` | Service level, fill rate, data-quality score |
| `StackedBars` | Value by warehouse split by stage or status |
| `Timeline` / `Gantt` | MRP supply vs demand, purchase orders, commitment dates |
| `BomTree` | Bill of materials as an expandable node graph |
| `Radar` | Supplier scorecard (price, lead time, on-time, quality, risk) |
| `Waterfall` | Cost method comparison (FIFO vs weighted average vs standard) |

**Backend need:** trends need a time bucket. If `QueryPlan` lacks one, add a `date_trunc` dimension op (day/week/month) under tests, and a `value_over_time` metric computed from the movements dataset. Synthetic tenants get 12 months of movement history (flagged synthetic).

---

## 5. Screens

### 5.1 Public landing page (`/`) — new
Same Next.js app, statically rendered, no API calls, < 100 KB JS. Signed-in users go straight to the app.

1. **Hero:** one-line promise ("Know every unit, every cost, every risk — and ask why."), sub-line, primary CTA *Request a demo*, secondary *Sign in*. Visual: an animated, synthetic product frame (overview + an Analyst answer typing out), labelled "Synthetic demo data".
2. **Proof strip:** "Read-only by design · Every number traceable · Works with SAP, Odoo and SQL warehouses" (text, no third-party logos).
3. **Problem → outcome:** three cards (dead stock and cash tied up; stock-outs and late customer orders; nobody trusts the numbers).
4. **Feature tour:** sticky scroll sections — Command centre, AI Analyst, Planning & commitment protection, Suppliers, Reports. Each with a real component rendered on synthetic data.
5. **How it works:** Connect (read-only) → Model (canonical inventory) → Ask (AI + dashboards), with a small animated diagram.
6. **Trust & security:** read-only connectors, role and warehouse scope, provenance, audit trail, AI never writes SQL, data stays in your region.
7. **FAQ** and **final CTA**; footer.

### 5.2 Sign-in — redesign
Split screen: form left, rotating product visual + one customer-value line right. Clear "Development sign-in" label while auth is dev-only.

### 5.3 App shell
Refine rail (groups Monitor / Analyze / Plan / Procure / Govern stay), add **Alerts centre** (bell, unread count, from insights), user menu with settings (theme, locale, number format, default warehouse), global **Ask** bar that opens the Analyst with the current screen as context.

### 5.4 Overview → Executive command centre
Row 1: hero KPIs with sparkline + delta (value, items, below reorder, expiring, at-risk orders, data quality score). Row 2: `TrendArea` value over 12 months + insight feed. Row 3: `Treemap` by group, `ParetoChart` ABC, `StackedBars` by warehouse. Row 4: planning tiles (fulfilment risk, shortages, upcoming procurement, supplier on-time). Closes `UI_UX_IMPLEMENTATION_STATUS` "Executive dashboard: not done".

### 5.5 Inventory + Material 360
Virtualised grid (server-paged, sticky header and first column, column chooser, density toggle), multi-select filter chips (UX-16), saved views. Row click → **Material 360** drawer/page: stock by warehouse, movement timeline, cost methods waterfall, lots and expiry, where-used (BOM), suppliers and lead times, open orders, provenance. Closes UX-07, UX-08, UX-13 (card rows on mobile).

### 5.6 Risks
`RiskMatrix` (value × days), expiry `HeatCalendar`, dormant ageing buckets (0–90, 91–180, 181–365, 365+), each bucket clickable.

### 5.7 Costs
Item picker with search (UX-14), `Waterfall` across methods, history of unit cost.

### 5.8 Planning, Commitments, Suppliers, Master data
MRP `Timeline` per item (supply vs demand vs safety stock), `BomTree`, commitment Gantt with risk colouring, supplier `Radar` and lead-time distribution, duplicate-item side-by-side compare.

### 5.9 Reports
Gallery of report cards with a thumbnail preview (UX-15), schedule placeholder (disabled until background jobs exist).

### 5.10 Admin › Data sources
Connection status, last refresh, row counts, mapping health and drift, data-quality score trend (ISSUES #39 rest, UX-17).

### 5.11 Assistant → "Lumiant Analyst" workspace
Full page and dock share one renderer:
- Conversation threads (left), answer canvas (centre), "how I got this" trace (right, collapsible).
- Answers stream token by token; numbers render as chips that link to their source row.
- **Inline charts** in answers (tool outputs gain a `chart` block: bar, line, donut, table).
- **Citations** for definitions and policies (from the knowledge index, §6).
- Suggested follow-ups per answer and per page; "Pin to overview"; export answer as PDF/CSV.
- Clear states: thinking, running tool N of M, withheld (grounding failed), AI off.

### 5.12 Cross-cutting UX
First-run tour (4 steps), keyboard shortcuts sheet (`?`), skip link (UX-18), consistent number formatter everywhere (UX-11), locale and 24-h time (UX-20), empty/error states with illustrations, no raw error text (UX-03).

---

## 6. Lumiant Analyst v2: Gemini + grounded RAG

**What "RAG" means here.** Inventory questions are answered by **retrieving numbers through the secured query engine** (structured retrieval), plus **retrieving knowledge** (definitions, policies, glossary, item text) through a vector index. The model never writes SQL and never invents a figure; ADR-0002 is unchanged.

```
question + screen context + history
        │
        ▼
 ① Retrieve knowledge ── vector + keyword search (tenant-scoped) ──► glossary, metric definitions,
        │                                                            policies, item master text, insights
        ▼
 ② Gemini plans (function calling, up to 6 rounds, parallel calls)
        │   tools: 13 inventory + 8 planning tools  +  NEW query_inventory(QueryPlan)  +  NEW find_items (semantic)
        ▼
 ③ App validates each call ─► scope injected ─► query engine ─► rows + provenance + audit
        │   (loop back to ② with results until the model says "done")
        ▼
 ④ Gemini writes the answer from tool results + cited knowledge chunks
        ▼
 ⑤ Grounding guard: every number must exist in a tool result; every definition must cite a chunk
        ▼
 ⑥ Stream: text tokens, chart blocks, citations, follow-ups
```

### 6.1 Build steps
1. **Live Gemini switch-on** (synthetic tenant only): owner puts the key in `services/api/.env`; set `ai.external_provider_approved: true` on `demo-alpha` and `demo-delta` only. Smoke test, then close the live part of ISSUES #13.
2. **Multi-step loop:** replace single `decide → compose` with a bounded loop (max 6 rounds, max 12 tool calls, per-turn timeout, token budget), keeping the rule-based provider as the offline fallback.
3. **`query_inventory(QueryPlan)` tool:** expose the existing validated plan (already allowed by ADR-0002) so the model can ask any grouping/filter/measure the catalog supports, not only the named analyses. This is the single biggest jump in "answers all sorts of things".
4. **Knowledge index (`lumiant.knowledge`):** chunk and embed (Gemini `gemini-embedding-001`; offline fallback DuckDB full-text/BM25) the canonical catalog descriptions, `INVENTORY_CALCULATIONS.md`, `CLASSIFICATIONS.md`, the terminology layer (incl. Arabic), tenant glossary, item master text, and current insights. Stored per tenant in DuckDB; every chunk carries tenant and warehouse scope; retrieval filters by the principal's scope before ranking.
5. **Semantic item resolution:** "the blue 10 mm bolts in Riyadh" → item ids via embeddings + codes, then the normal tools.
6. **Chart blocks** in `ToolOutput` and the SSE stream; the UI renders them with the chart kit.
7. **Token streaming** of the composed answer (grounding check runs on the final text before the "verified" tick; a failed check replaces the text, as today).
8. **Conversation memory:** server-side threads per user (titles, last 20 turns), deleted with the user's data.
9. **Evaluation:** golden set of 150 questions (existing evals + new multi-step and knowledge questions) run against live Gemini; report accuracy, groundedness, latency p50/p95 and cost per answer. Gate: ≥ 95 % correct or honestly declined, 0 silently wrong.
10. **Guardrails kept:** scope checks, cost-field permissions, prompt-injection tests on item text and documents, audit of every tool call, AI off for the client extract until Q-013 is answered.

### 6.2 Gemini key: how to hand it over
Do **not** paste the key in chat. Put it in `services/api/.env` (git-ignored):
```
LUMIANT_AGENT_PROVIDER=gemini
LUMIANT_GEMINI_API_KEY=<your key>
LUMIANT_GEMINI_MODEL=gemini-flash-latest
```
A free-tier key is fine for synthetic data only; Google may use free-tier prompts. A paid key is required before any client data could reach Gemini, and that still needs the client's approval (Q-013).

---

## 7. Speed and quality budgets (acceptance criteria)

| Metric | Budget |
|---|---|
| Landing page LCP (4G, mid laptop) | < 1.5 s; JS < 100 KB gzip |
| App route change (warm) | < 300 ms to skeleton, < 1 s to data on synthetic tenants |
| Overview first load (cold, prod build) | < 2.0 s LCP |
| Inventory grid | 10 000 rows scroll at 60 fps (virtualised) |
| Analyst first token | < 1.5 s p50; full answer < 6 s p50 on Gemini Flash |
| Accessibility | axe: 0 serious/critical; full keyboard pass; contrast gate both themes |
| Regression | API tests, web unit, e2e stay green; new e2e per new screen |

Techniques: server components for static shells, route prefetch, React Query persisted cache with stale-while-revalidate, code-split charts (`next/dynamic`), API response caching per tenant/scope (insights already cached), virtualised tables, image-free illustrations, font subsetting.

---

## 8. Productisation (prototype → product)

| Item | Note |
|---|---|
| Real sign-in | OIDC code exists (`test_oidc.py`); needs an IdP choice (Q-010). Until then the login page states "development sign-in" |
| Demo request capture | Landing form stores requests in the app DB with an admin list; sending email needs a provider choice |
| Settings | Theme, locale, number format, default warehouse, notification preferences |
| Alerts | Insight-driven, in-app first; email later |
| Observability | Front-end error capture and web vitals to the API log (no third-party service without approval) |
| Deployment | Docker images exist and CI builds them. **Any real deployment needs the owner's written authorization** (project hard rule) |

---

## 9. Phases and order

| Phase | Scope | Depends on |
|---|---|---|
| **P1 · Foundations** | Design system v2 tokens, chart kit, `/design` showcase, number formatter, perf baseline measurements | — |
| **P2 · Analyst v2** | §6 steps 1–10 | Owner's Gemini key in `.env` (step 1 only; steps 2–6 can be built and tested with fake clients first) |
| **P3 · Landing + sign-in** | §5.1, §5.2 | P1 |
| **P4 · Command centre** | §5.4 + time-bucket metric + synthetic history | P1 |
| **P5 · Inventory + Material 360** | §5.5 | P1 |
| **P6 · Analysis screens** | §5.6–5.10 | P1, P4 |
| **P7 · Product polish** | §5.3, §5.12, §7 budgets, axe, §8 items | all |

P1 and P2 can run in parallel (web vs API). Each phase ends with tests, a browser check, logs, and a commit only when the owner asks.

---

## 10. Decisions for the owner

| # | Question | Proposed default |
|---|---|---|
| D1 | Keep the official navy / gold / teal brand palette and elevate it, or a new palette? | **Keep and elevate** (it comes from the official logos) |
| D2 | Landing page in the same Next.js app at `/`? | **Yes**, app routes unchanged |
| D3 | Where do demo requests go? | **App DB + admin list** now; email later |
| D4 | Pricing section on the landing page? | **No** until pricing exists |
| D5 | Expose `query_inventory(QueryPlan)` to the model (within ADR-0002)? | **Yes** |
| D6 | Generate 12 months of synthetic movement history for trend charts? | **Yes**, flagged synthetic |
| D7 | Start order | **P1 + P2 together**, then P3 |
