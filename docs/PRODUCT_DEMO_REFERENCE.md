# Lumiant AI — Product Demo Reference

A practical sheet for producing the demo video. Everything here was **verified on 11 Nov 2026** on `main` at `758153d`, synthetic data, signed in as **Alex Admin** (Demo Alpha Manufacturing) unless stated. Figures come from the generated demo data. They stay the same after regenerating, but the "Data as of" time and day-based counts (dormant, expiry) can shift with the date. Full detail and evidence: `docs/PRODUCT_FUNCTIONALITY_AUDIT.md`.

---

## Before recording

| Do | Why |
|---|---|
| Regenerate data: `services/api` → `lumiant-synthetic generate --all` | The header "Data as of" shows a fresh time instead of "stale" |
| Record from a **production build** (`apps/web`: `pnpm build` then `pnpm start`), API on port 8000 | Development mode shows a Next.js "N" badge over "Sign out". The production build wasn't re-checked in this audit |
| Browser window 1440 × 900 or larger; pick light or dark theme (top-right toggle) | Layout tested at 1440 × 900 |
| Sign in as **Alex Admin** | All features and values visible |
| Keep assistant questions under **20 per minute** | The server rate-limits chat at 20/min ("Too many requests…") |
| Stay on **Demo Alpha** | Demo Gamma shows error and "Needs more data" states; Beta is fine but has two currencies |
| Keep the **SYNTHETIC DEMO DATA** badge in shot | Required by the project's rules; never present it as customer data |

---

## Screen names and navigation paths

| Screen (exact title) | How to get there | Key visual elements |
|---|---|---|
| Login — "LUMIANT · Inventory intelligence platform" | `http://localhost:3000` | Banner "Development authentication — not for production"; user cards per company |
| **Inventory position** (Overview) | Nav › Monitor › **Overview** (`G O`) | KPI strip · "Inventory at a glance" (4 areas) · "What needs attention" · 4 charts · "Items below reorder level" |
| **What would you like to do?** (Explore) | Nav › Monitor › **Explore** (`G E`) | 8 task cards |
| **Stock on hand** (Inventory) | Nav › Analyze › **Inventory** (`G I`) | Search, 4 filters, sortable table, Source |
| **Inventory risks** | Nav › Analyze › **Risks** (`G R`) | Tabs: Excess stock · Dormant stock · Expiring lots · Data quality |
| **Cost analysis** | Nav › Analyze › **Costs** (`G C`) | Cost comparison (4 methods + reconciliation) · Computed ABC vs assigned |
| **Ask about your inventory** (Assistant) | Nav › Analyze › **Assistant** (`G A`) | 7 starter questions, chat with trace, charts, tables |
| **Reports and exports** | Nav › Govern › **Reports** (`G P`) | Report picker; CSV / Excel / Print |
| **Onboarding and oversight** (Admin) | Nav › Govern › **Admin** (`G D`) | Tabs: Connection and schema · Capabilities · Reconciliation · Audit log |
| **Analyst** dock | Top-right **Analyst** button, any ✦ icon, right-click, or a question chip | Right-hand panel: selection chips, live steps, answer, Source, Pin, 👍/👎, input "Ask about the selection…" |
| Command palette | `Ctrl K` (or `/`) | Pages, actions, "Search pages, materials or ask" |
| Lens | Press `L` | Banner "Lens — click anything to analyze · Shift-click to compare" |

---

## Verified actions (what happens on screen)

| Action | Result seen |
|---|---|
| Overview loads | Inventory value **USD 2,767,451.83** · Items in stock **585** · Stock lines **1,160** · Below reorder level **80** ("62 item–warehouse pairs have no reorder policy") |
| Click **Source** (page icon) on Inventory value | "Provenance slip · inventory_value_total · v1": Source "Synthetic DuckDB warehouse — SAP-style naming", Objects ZV_STOCK, Fields currency ← ZV_STOCK.WAERS, stock_value ← LABST × VERPR, scope "all warehouses in tenant", "Split by currency (never summed across)", Rule text |
| Four areas | Stock position: **South Plant — Raw Materials Store, USD 1,128,850.12 · 41%**; **Mech Spares, USD 989,855.74 · 36%** · Replenishment: **26** above maximum, **62** no policy · Stock health: **49** dormant (180 days), **29** expired (9 more within 60 days) · Cost and data trust: **3** checks, **600** items |
| Click chip **"Which lots have already expired?"** | Analyst opens. Steps: "Understanding the question — checking lot expiry dates" → "Checking lot expiry dates · 15 rows · 88 ms" → "Checking every number against the results — every number traced to the results". Answer: "29 lots on hand have already expired and 9 more expire within 60 days. The table shows the first 15." + table (Item, Warehouse, Lot, Quantity, Expires, Days left) |
| Click a bar in **Value by warehouse** | Analyst chip "Warehouse 2100 · South Plant — Raw Materials Store" |
| With that warehouse selected, ask **"Break this down"** | "The highest item group in warehouse 1100 is ELECTRICAL with USD 208739.72310000…" + "Value by item group in warehouse …" chart + "Top 5 items by on-hand value" table *(tested via the API with warehouse 1100 selected)* |
| ✦ **Analyze** on Items in stock | Analyst opens with chip "Metric · Items in stock" and suggestions "Break this down" / "Which items make up most of the value?". Clicking "Break this down" → quantity by warehouse, per unit (EA, KG, L) |
| Inventory › Warehouse **2100** | "532 lines match" |
| Inventory › click **VALUE** header twice | Descending: **2119000124 Pump impeller 175 mm · 15 EA · USD 4,175.38 · USD 62,630.67** first |
| Inventory › ABC **A** | "245 lines match" |
| Right-click an inventory row | Analyst chip "Item 2119000124" |
| Risks › Expiring lots | "29 expired · 9 expiring within 60 days"; window choices 30 / 60 / 90 / 180 days |
| Costs › Item id **2119000124**, Warehouse **2100 · South Plant — Raw Materials Store**, **Compare** | Moving weighted average **USD 4,175.38** (value 66,806.05) · FIFO **USD 4,180.28** (66,884.49) · Latest receipt cost **USD 4,180.28** (2026-10-20 · 4900079176) · Latest valid purchase price **USD 4,180.28** (2026-10-09 · 4500007336) · "Reconciliation with the source valuation … Recomputed average matches." + FIFO layers |
| Costs › A covers up to **0.80**, B **0.95**, **Classify** | "584 items ranked in USD; 116 differ from the class assigned in the source" + matrix + top-40 table |
| Reports › **Items below reorder level** | 80 rows, buttons **CSV · Excel · Print**, header block with organisation, source and time |
| Admin › Connection and schema | "Mapping matches the source · connection healthy", 10 objects "ok" |
| Admin › Audit log | Rows: when, user, action, decision, rows, ms — "Result values and filter values are never stored." |
| Sign in as **Ana Analyst** | "Limited to 1 warehouse by your access scope"; Inventory value "Your role cannot view values"; 28 items, 35 lines, 5 below reorder; Costs and Admin gone from the menu; Inventory "Cost columns are hidden for your role" |
| `Ctrl K` | Palette with all pages, "Toggle light / dark theme", "Collapse / expand navigation", "Sign out" |

---

## Tested AI questions and actual responses

**Use these exact phrasings. Similar wording may not be recognised.**

| Ask exactly | Actual answer (first sentence) | Visual |
|---|---|---|
| Which items are below reorder level? | "80 item–warehouse pairs are below their reorder level. The lowest coverage is 1104000046 in 1110: 0.0000 on hand against a reorder level of 69.1930. 62 stocked pairs have no reorder policy, so they cannot be assessed." | Table |
| Which items make up most of the value? | "108 of 585 stocked items (18.5%) hold 80% of the USD value; the top 10 hold 27.9%." | Table with cumulative share |
| Show inventory value by warehouse | "The highest warehouse is South Plant — Raw Materials Store with USD 1128850.11776790." | Bar chart (6 warehouses) |
| Show the highest-value items | "The highest-value item is 2119000124 (Pump impeller 175 mm) at USD 133381.83870000." | Top-10 table |
| Which items have excess stock? | "26 item–warehouse pairs hold more than their maximum stock policy. The largest is 2103000047 in 2100…" | Table |
| Which items have not moved in six months? | "49 item–warehouse pairs have stock but no issue in the last 180 days (as of 2026-11-11)." | Table |
| Which lots are nearing expiry? | "29 lots on hand have already expired and 9 more expire within 60 days. The table shows the first 15." | Table |
| Which items have incomplete master data? | "3 of 11 master-data checks found gaps among 600 items. The largest is: Stocked item–warehouse pairs without a reorder policy (62)." | Checks table |
| What should I look at first? | "I found 7 things worth a look. The most important: 29 lots on hand are expired and 9 more expire within 60 days." | Insights table (~1.3 s) |
| Which items need special storage? | "166 items have recorded special storage requirements (a temperature range or a flammability class). This only reflects what is recorded in the item master; I do not infer requirements from item names." | Table |
| Break stock down by item group | "The highest item group is PACKAGING with EA 272530.0000. Results are shown separately per unit (EA, KG, L) and never added together." | Bar chart |
| *(follow-up)* what about quantity? | Re-runs the previous breakdown as quantity per unit | Bar chart |
| What is the latest price of item 2119000124? | "Item 2119000124 is held in 2 warehouses. Which one?" | Two choice buttons (1120, 2100) |
| Which materials have the highest obsolescence risk? | "I can't predict obsolescence: that needs product-lifecycle or equipment-status data, which isn't in the mapped inventory data… try 'Which items have not moved in six months?'" | Honest refusal — good for a "trust" moment |
| *(as Ana Analyst)* Show the highest-value items | "Your role can't view inventory values, so I can't rank items by value. I can rank by quantity per warehouse instead." | Governance moment |

**Do not ask on camera** (not understood or wrong):
- "What is the total inventory value?" / "How much inventory do we have?" (the second gives a misleading item-lookup reply)
- "Show me all A-category items" · "Which items have the highest inventory value?" · "Where is item X held?" · "Give me details of item X" · "Show me the available inventory classifications" · "Which supplier do we spend the most with?" · forecasting questions
- "Compare warehouses 1100 and 2100" (returns all warehouses; to compare, use Lens Shift-click instead)
- Arabic or other languages

---

## Best demonstration sequence (7 steps, all verified)

| # | Exact action | Ask | What appears | What the viewer should notice | Why it matters |
|---|---|---|---|---|---|
| 1 | Sign in as **Alex Admin** → Overview | — | KPI strip: USD 2,767,451.83 · 585 · 1,160 · 80 | One screen, no question needed, live numbers, synthetic badge | Instant inventory position for executives |
| 2 | Scroll to **Inventory at a glance** and **What needs attention** | — | Four areas; insight "29 lots on hand are expired…" (Critical) | The product tells you what to look at, with suggested actions | Prioritises action, not just reporting |
| 3 | In **Stock health**, click **"Which lots have already expired?"** | (chip) | Analyst opens; three live steps; sentence; table | "Checking every number against the results — every number traced to the results" | Answers are traceable, not guessed |
| 4 | Click **Source** on Inventory value (or under an answer) | — | Provenance slip with tables, fields, rule, scope | Every figure shows exactly where it came from | Auditability; trust with finance |
| 5 | **Inventory** → Warehouse 2100 → click **VALUE** twice | — | 532 lines; Pump impeller 175 mm at the top | Fast search, filter and sort over every stock line | Day-to-day operational use |
| 6 | **Assistant** → type **"Which items make up most of the value?"** | as shown | "108 of 585 stocked items (18.5%) hold 80% of the USD value…" + table | A plain-English question becomes a precise business insight | Where to focus counting and approvals |
| 7 | **Costs** → 2119000124 / 2100 → **Compare** | — | Four costing methods + "Recomputed average matches" | Deterministic, reconciled cost analysis | Finance-grade numbers |
| *Close* | Sign out → sign in as **Ana Analyst** → Overview | — | "Limited to 1 warehouse"; "Your role cannot view values" | Same product, governed per role and warehouse | Enterprise access control |

Optional extras: `Ctrl K` palette and `L` Lens for a power-user beat; Reports › Items below reorder level → **CSV / Excel / Print** for the hand-off to other teams.

---

## Limitations the video creator must know

- **Synthetic data** in fictional companies. Don't call it a customer, and don't say "connected to SAP / Oracle / Odoo": no ERP is connected.
- **No AI model runs** in this setup. The assistant uses built-in matching, and the footer under each answer says "Built-in matching". Avoid saying "AI-powered" or "GPT/Claude/Gemini answers" unless an approved provider is switched on first.
- Assistant sentences show **raw unrounded numbers** (e.g. "USD 1128850.11776790"); frame shots on the formatted chart or table.
- **English only**; uncommon phrasings get "I can't answer that yet".
- Avoid **Demo Gamma** (error card, blank warehouse names, coded groups).
- The **"N" dev badge** appears in development mode; record from a production build.
- After using ✦ Analyze, the old selection chip stays in the Analyst. Click **Clear** (top right of the dock) before asking something unrelated.
- No purchasing or supplier analysis, item-detail page, forecasting or LIFO.
- The day-based counts (dormant, expiring) depend on the date and data generation; rehearse on the day of recording.
