# Frontend

Status: **Implemented and tested (M1)**. Code in `apps/web/`: Next.js 16.4 App Router (per-request rendering; `cacheComponents`/`partialPrefetching` were turned off for the nonce CSP, ADR-0007), React 19.3, TypeScript 5.9, Tailwind 4 (Turbopack loader), React Query 5.104, Recharts 3.10, Radix (popover, dialog, tooltip), cmdk 1.1 (command palette), Motion 14.1 (`motion/react`), Inter (`inter-ui` 4.1.1) with Geist Mono (`geist` 1.7) for identifiers, lucide icons. Visual language: ADR-0011.

## Routes (M1)

| Route | Purpose | Permission (from `/api/auth/me`) |
|---|---|---|
| `/login` | Dev user picker (labelled *Development authentication*) | public |
| `/overview` | KPI row, value charts, below-reorder table | `dashboard:read` |
| `/inventory` | Filterable, searchable, sortable, paginated stock lines | `inventory:read` |

Navigation shows only routes that exist **and** that the user may access. No placeholder pages.

## Data fetching

- `src/lib/api.ts`: typed fetch wrapper (same-origin `/api/*`, `credentials: "same-origin"`, `X-Requested-With: lumiant` on POST); throws `ApiError{status, code, message, requestId}` (status 0 = network).
- React Query for caching, retries off for 4xx, loading/error states per widget.
- The error envelope is validated with zod (`lib/api.ts`); success payloads are typed. Non-JSON error bodies are never shown to users.
- Pages are client components; no server component reads cookies, so the API stays the only enforcement point.
- `usePageMe()` reads the session only after hydration (the shell may resolve it first), which prevents hydration mismatches.
- The shell always renders page content (Next 16 instant-navigation validation requires it); the session state only affects the chrome.
- Next keeps the previous route mounted but hidden (React Activity): tests must scope locators to visible regions.

## Components

| Component | Notes |
|---|---|
| `shell/AppShell` | "command center" shell (see § Shell): collapsible icon rail (permission-filtered nav in Monitor / Analyze / Govern groups, sliding active marker, pending-navigation dot, user card with roles and scope, sign out, collapse toggle), glass command bar (tenant, **SYNTHETIC DEMO DATA** tape, palette trigger, data as-of turning amber when stale, theme toggle), route transition |
| `shell/CommandPalette` | ⌘K / Ctrl+K palette: pages, materials, "Ask: …", actions (see § Command palette) |
| `shell/useShortcuts`, `shell/nav`, `shell/rail-state` | keyboard shortcuts; the single nav definition (`NAV`, `navFor(sections)`); rail state on `<html data-rail>` |
| `overview/KpiStrip` | inventory value per currency (never summed), items in stock, stock lines, below-reorder count + pairs without policy; locked state for no-cost roles |
| `data/ValueBars` | Recharts horizontal bars for a value metric; currency switcher when >1 currency; excluded-lines note in subtitle |
| `overview/BelowReorderPanel` | lowest coverage first, coverage bar, shortfall, paging |
| `inventory/InventoryExplorer` | URL-state filters, debounced search, server sort + paging, cost columns only with `cost:read` |
| `data/ProvenanceButton` | "provenance slip": source, objects, canonical ← physical fields, user filters, access scope applied by permissions, split-by, rule + status, as-of, rows/duration, SQL (only if the API sent it) |
| `data/Panel`, `ErrorState`, `Skeleton`, `Warnings`, `Pager` | shared frame and states: loading, empty, error (message + request ref), forbidden |

### Primitive layer (`components/ui/`, ADR-0011)

Pages compose these; they do not style controls by hand. All consume tokens, all are built with `clsx` only. A class passed by a caller must not repeat a property the primitive already sets (height, width, padding, font size, text colour): Tailwind does not order two utilities for the same property by their position in the class list, so the result would be arbitrary. Callers add layout classes (margin, grid placement, `figure`, `code`) only.

| File | Exports | Notes |
|---|---|---|
| `button.tsx` | `Button`, `IconButton`, `buttonClass()` | variants `primary` (accent fill), `secondary` (default: bordered), `ghost`, `soft` (accent tint); sizes `sm` 28 px, `md` 36 px, `lg` 40 px; `type="button"` unless stated; 1 px press feedback; `buttonClass()` gives links the same look |
| `field.tsx` | `Field`, `Input`, `Textarea`, `Select`, `SearchInput` | label above the control (sentence case, 12 px), optional hint below; one 36 px control box with a `control-line` boundary; controls fill their parent, so width is set on the `Field` (`className="w-36"`), never on the control; `Select` is the native element with a chevron |
| `tabs.tsx` | `Tabs`, `Segmented` | `role="tablist"` / `role="tab"` / `aria-selected`; the underline slides with `LAYOUT_SPRING` |
| `badge.tsx` | `Badge`, `Chip` | `Badge` tones neutral / accent / signal / ok for states (always with words); `Chip` is a clickable question or choice |
| `table.tsx` | `DataTable`, `HeadRow`, `Th`, `Tr`, `Td`, `CodeName` | the one table recipe (13 px rows, hairlines, quiet hover); columns 24 px apart, first and last cell on the panel inset; right-aligned cells never wrap; a long table scrolls inside the panel (max 70 % of the window) with a sticky header; text is `ink-2`, right-aligned cells (numbers) and the name in `CodeName` are full `ink`; colour a value with a span inside the cell, not on the cell; `Th` takes `sort` and sets `aria-sort`; `CodeName` is the two-line code + name cell. |
| `page-header.tsx` | `PageHeader` | title (`text-page`), one line of description, optional slot on the right; one per page, no label above the title |
| `empty-state.tsx` | `EmptyState` | a plain sentence, optional icon and hint |
| `float.ts` | `floatSurface`, `tooltipSurface` | class recipes for popovers, menus and tooltips |

### Data label (M8)
`components/shell/synthetic-tape.tsx` exports `DataBadge({ classification, synthetic })`: the client-extract badge
("CLIENT EXTRACT · CONFIDENTIAL · LOCAL", `data-testid="client-extract-badge"`) for `customer_extract` tenants, the
synthetic tape for generated data, nothing for live customer data. Used in the header and per tenant on the login
page; provenance slips show `CLIENT EXTRACT` too. The explorer hides columns whose field the API did not return
(sources without lots, ABC on item or warehouse names) and shows a stock-status filter when the source has one.
Data-quality checks may have status `info` and a `share` (percent string).

## Formatting

Decimal strings formatted with `Intl.NumberFormat` (string input preserves precision). Currency always shown with its code. Quantities shown with UoM.

## Design tokens

Graphite and emerald (ADR-0011) in `src/app/globals.css` (raw variables on `:root`, mapped to Tailwind utilities by `@theme inline`). Token names did not change in the M11 visual refresh; only values did.

- **Theme follows the system until the user chooses.** `:root` holds the dark values; `[data-theme="light"]` holds the light ones. The same-origin `public/theme-init.js` (no inline script, CSP-safe) writes the effective theme before first paint: a saved choice (`localStorage` `lumiant-theme`) wins; with none saved, a light OS sets `data-theme="light"`, a dark OS leaves the attribute off, and a later OS change is followed live. Toggle: `shell/theme-toggle.tsx` (`toggleTheme()` flips from the attribute and saves; the icon follows the theme through the `light:` variant, so server and client markup match). "Theme: match system" in the palette (`matchSystemTheme()`) forgets the saved choice. Without JavaScript the app is dark.
- **Planes:** `bg` (page) → `surface` (panels, rail, dock) → `surface-2` (hover, table head, tiles) → `surface-3` (popovers, menus). **Ink:** `ink`, `ink-2`, `ink-3`. **Lines:** `line`, `line-strong` (separators, quiet buttons), `control-line` (form-control boundary, ≥ 3:1). **Accents:** `accent` (emerald, UI only: focus, active, primary action; `accent-strong` on hover; `accent-ink` on accent fills), `signal` (amber, attention only), `ok`; `-soft` tints for fills.
- **Shape:** one radius rule. `rounded-control` 8 px (buttons, inputs, selects, tabs, tooltips), `rounded-panel` 12 px (panels, cards, filter bars, chat bubbles), `rounded-float` 14 px (popovers, palette), `rounded-full` (chips, badges, avatar). Tailwind's `rounded-sm/md/lg/xl` are not used outside `components/ui/`.
- **Glass and elevation:** `glass` utility (translucent `--glass` + 16 px backdrop blur) only for chrome that floats over scrolling content (command bar); the palette uses `glass-strong`. The rail and the Analyst dock are solid `surface`. Under `prefers-reduced-transparency` glass becomes solid. `panel` utility is the one card recipe (surface, hairline, panel radius, `shadow-e1`). Shadows `shadow-e1/e2/e3` (dark: inner top highlight + drop shadow; light: tinted to the ink, never pure black). The active or selected edge is `shadow-ring` (a 1 px accent hairline) or an accent bar; there is no glow. The page background is flat: no grid, no radial lights.
- **Contrast (computed with the brand-system `contrast.mjs`, TEST_RUNS S07-1):** every text token passes WCAG AA on every plane in both themes. Worst cases — dark: ink 13.5:1, ink-2 7.9:1, ink-3 5.2:1, accent 8.0:1, signal 7.4:1 (all on surface-3), status-critical 4.5:1 (on surface-2); light: ink-3 5.2:1, accent 5.0:1, signal 5.2:1, status-critical 4.7:1 (on surface-2); accent-ink on accent 8.4:1 dark / 5.7:1 light. `control-line` 3.2–4.0:1 dark, 3.4–3.8:1 light (≥ 3:1, WCAG 1.4.11). Text set in `--status-warning` is not allowed in light (1.8:1 on white); warning labels use `signal`.
- **Data viz:** `--viz-1…8` is the dataviz reference palette in its fixed order (blue, orange, aqua, yellow, magenta, green, violet, red) with separate light and dark steps; `--viz-grid`, `--viz-axis`, `--viz-cursor` for chart chrome; `--status-good/warning/serious/critical` are reserved for state and always shown with an icon + label. UI accents are never series colors. Single-series bars use slot 1 with 4 px rounded data ends, a recessive grid and text in ink tokens. Validation (dataviz `validate_palette.js`, TEST_RUNS D1-2): light on #ffffff and dark on #0f1318 both pass the lightness band, chroma floor, adjacent-pair CVD separation (worst ΔE 9.1 light / 8.4 dark) and the normal-vision floor (19.6 / 19.3). In light mode aqua, yellow and magenta are below 3:1 against the surface, so a chart using those slots must carry direct labels or a table view (relief rule). Chart forms where every pair can be adjacent (scatter, maps, small multiples) may use only the first three slots.
- **Typography:** Inter (variable, optical-size axis, features `ss01` open digits and `cv05` l with a tail) for all text and numbers; `.figure` sets tabular figures so columns align without a monospace. Geist Mono only through `.code` (slashed zero) for identifiers: item codes, warehouse and lot ids, request refs, usernames, SQL, `kbd`. Rule of thumb: a quantity, amount, count or date is `.figure`; something a person copies into another system is `.code`. Both fonts are woff2 files shipped in npm packages (`inter-ui`, `geist`) and loaded with `next/font/local`: self-hosted, no font CDN at build or run time (CSP `font-src 'self'`). Scale (`@theme`): `text-caption` 11, `text-xs` 12, `text-dense` 13 (tables), `text-sm` 14 (body), `text-title` 15 (panel title), `text-section` 18, `text-page` 26 (page title, weight 600, tracking −0.022em), `text-kpi` 28. `.eyebrow` (11 px uppercase, tracking 0.06em) is only for table column heads; page titles carry no label above them and form labels are sentence case. Icons: lucide at one stroke width (1.75, set in CSS), sizes 14–18. Chart category labels use the sans on one line, truncated, with a `<title>` holding the full label.
- **z scale:** `--z-sticky` 20 (command bar), `--z-rail` 30, `--z-nav` 40 (mobile tab bar), `--z-overlay` 50 (popovers, tooltips), `--z-palette` 60; used as `z-(--z-…)`, never literal values.

## Motion

Single source of truth: `src/lib/motion.ts` (`EASE`, `DUR`, `STAGGER`, `RISE`, `Z`, `LAYOUT_SPRING`, `enterDelay()`, `floatIn()`), mirrored as CSS variables (`--ease-*`, `--dur-*`, `--rise`) in `globals.css` — change both together. Values suit a dense working tool: `fast` 140 ms (hover/press; also Tailwind's default transition), `base` 220 ms (palette, route fade, popovers), `slow` 360 ms, `enter` 420 ms (entrance reveal), stagger 50 ms capped at 8 steps, lift 6 px. Three curves: `out` (expo-out, default), `inOut` (symmetric moves), `pop` (one accent overshoot). The one exception is a critically damped spring for the shared-layout active-nav marker, so an interrupted move keeps its velocity.

- **Who animates what.** Entrance reveals are CSS (`.rise`, `.route-enter`, `.pop-enter`; keyframe names start with `enter-`): they work before JavaScript runs and cost nothing. Motion (`motion/react`) is used only for interactive and layout motion: the palette's enter/exit (`AnimatePresence` + Radix `forceMount`) and the rail's sliding active marker (`layoutId`). Recharts animation stays off. Only `transform` and `opacity` animate; the rail width changes instantly (animating it would re-lay out every chart on every frame).
- **Staggers:** every entrance delay comes from `enterDelay(i)`; no page passes a hand-built `animationDelay` (migrated in M11). Buttons and chips give 1 px press feedback (`active:translate-y-px`).
- **Reduced motion** (`prefers-reduced-motion: reduce`): no travel, no loops; content still arrives, by opacity. CSS swaps `.rise`/`.pop-enter` to `enter-fade` and stops the skeleton shimmer; `<MotionConfig reducedMotion="user">` (`components/providers.tsx`) drops transform/layout animation and keeps opacity; `floatIn(reduce)` removes scale and offset. e2e: `reduced motion: entrances fade in place instead of travelling`.
- **Background tabs (ISSUES #10, fixed).** A hidden tab produces no frames, so an animation started there rests at its first keyframe (opacity 0). `public/theme-init.js` sets `<html data-motion="off">` while the tab is hidden — CSS then removes every `enter-` animation, so content shows at its resting (final) state — and finishes every finite running animation. When the tab returns it removes the flag and immediately finishes the re-applied entrance animations, so nothing replays. `MotionGlobalConfig.skipAnimations` follows visibility for Motion. The resting style of every animated element is its final state. Tests: unit `public/theme-init.js` (4) and e2e `entrance animations never leave content faded in a background tab`.

## Shell

- **Layout:** CSS grid `[var(--rail-w)] [content]` from `md` up; rail 15 rem expanded, 4.25 rem collapsed. Below `md` the same `<nav aria-label="Main">` becomes a fixed, horizontally scrolling bottom tab bar (icon + label, safe-area padding); the brand mark and sign-out move into the command bar and `main` gets bottom padding.
- **Rail state** lives on `<html data-rail="collapsed">`, applied before first paint from `localStorage` (`lumiant-rail`), so there is no layout shift or hydration mismatch. `rail-state.ts` is the only writer and exposes `useRailCollapsed()` (external store). Collapsed labels are `sr-only` (the `rail-collapsed:` variant), never removed, so links keep their accessible names; a Radix tooltip shows the label and its shortcut.
- **Rail look (M11):** solid `surface` with a hairline; the active item is a `surface-2` fill with an accent bar on its left edge and an accent icon (the marker still slides with `layoutId`). Group names are sentence case.
- **Command bar** (`<header>`, the page banner): tenant name, data-badge slot (`SyntheticTape`; the badge component belongs to the data-intake work), palette trigger ("Search, jump or ask…", ⌘/Ctrl K), `data-as-of` slot, theme toggle. Glass, sticky.
- **Route transition:** the page is wrapped in `<div key={pathname} className="route-enter">`, a 220 ms opacity fade on every page change; search-param changes (explorer filters) do not remount. Nav links show a pulsing dot while their navigation is pending (`useLinkStatus`).

## Command palette

`shell/command-palette.tsx`: Radix Dialog + cmdk, opened by ⌘K / Ctrl+K anywhere, `/` outside text fields, or the command-bar button.

| Group | Source | Permission |
|---|---|---|
| Go to | `NAV` filtered by `Me.sections` (the API decides), with each page's G-shortcut | same sections as the rail |
| Materials | the existing `GET /api/inventory/balances?q=` (the explorer's permission-scoped, audited search; ≤ 50 stock lines → ≤ 8 distinct materials), debounced 200 ms, from 2 characters; opens `/inventory?q=<item code>` | only with the `inventory` section; never called otherwise |
| Assistant | "Ask: “…”" for any typed text (≥ 2 characters) → `/assistant?q=…`; when the assistant is already open the question is handed over in place (`lib/ask.ts` event), keeping the conversation | only with the `assistant` section |
| Actions | toggle theme, theme: match system, collapse/expand navigation, sign out | everyone |

Matching is word-prefix (`paletteFilter`: "inv" → Inventory), not cmdk's default fuzzy subsequence, which matched typed questions to unrelated pages ("valve" → Inventory). The palette never computes or shows a number; it only navigates.
The inventory explorer mirrors an outside change of the URL `q` (palette, back button) into its search box; its own debounced writes are skipped, so typing during the round trip is never overwritten.

## Analyst Lens (ADR-0010)

The "analyze anything" chat. `components/analyst/`:

| Piece | What it does |
|---|---|
| `store.ts` | one external store (no provider): dock open, Lens on, selections (≤ 5), the conversation, pinned answers (localStorage, per browser). `analyze(sel, {additive, ask})` points the Analyst at something; `ask(q)` streams an answer with the page, URL filters (`warehouse`, `item_group`, `stage`, `status`), selections and the last 6 questions/tools as context. Sets `data-dock` / `data-lens` on `<html>`. |
| `analyzable.tsx` | `analyzableProps(sel)` (data attributes the Lens reads), `<Analyzable>` wrapper, `AnalyzeButton` (spark icon; Shift adds to a comparison). Right-click on an analyzable element opens the Analyst with it selected (Shift + right-click keeps the browser menu); `A` on a focused wrapper does the same. |
| `lens.tsx` | Lens mode (`L`, or the dock's Lens button): every analyzable element is outlined, hover lifts it with the accent glow, a click selects it (capture phase, so the normal click does not run), Shift-click adds, Esc leaves. A status pill shows the mode. |
| `analyst-dock.tsx` | right-hand dock that stays open across pages (resizable 22–44 rem, width in `--dock-w`; wide screens pad `.app-main` instead of covering it). Context chips, selection-specific suggestions, streamed trace, answers with sources, Pin / pinned board, new conversation. |
| `answer-view.tsx` | shared answer rendering for the dock and `/assistant`: tables, bars (grow-in), the step trace, sources, feedback. |

What is analyzable: KPI tiles (`metric`), every value panel (`metric`), each bar (`warehouse` / `item_group` / `abc` / `stage`, picked by hover in Lens mode or by click), explorer rows (`item`), insight cards (`insight`). Labels are shown in chips but never trusted by the API.

`lib/agent.ts`: `streamChat` reads `POST /api/agent/chat/stream` (SSE) and falls back to `/api/agent/chat`; `toWire` trims selections to the API limits; `toHistory` sends questions and tools, never results.

**Insight feed** (`overview/insights-feed.tsx`): `GET /api/insights` as ranked cards (severity edge + icon + label, template title, metrics, Analyze → Analyst with the card's selection and question, Open → the page) and an "Unlock more analyses" list of gaps naming the missing source data.

## Keyboard shortcuts

| Keys | Action |
|---|---|
| ⌘K / Ctrl+K | open or close the palette (also inside text fields) |
| `/` | open the palette |
| `G` then `O` / `E` / `I` / `R` / `C` / `A` / `P` / `D` | Overview / Explore / Inventory / Risks / Costs / Assistant / Reports / Admin (granted pages only; 1.2 s window) |
| `[` | collapse / expand the rail |
| ⌘J / Ctrl+J | open or close the Analyst |
| `L` | Lens mode on / off (Esc leaves) |
| `A` | analyze the focused element (Shift: add to the comparison) |

Single-key shortcuts never fire while typing in an input, textarea, select or editable element, or with a modifier held. Links and buttons carry `aria-keyshortcuts`.

## Public landing page and chart kit (Product v2, S10)
- `/` is the public landing page (`components/landing/`), server-rendered with sample visuals labelled "Sample data"; a visitor with the development session cookie is sent to `/overview`. `src/proxy.ts` treats only `/` and `/login` as public. The demo form posts to `POST /api/public/demo-requests`.
- `/design` (signed in) shows every token, type size, control and chart in the current theme.
- `components/viz/` is the chart kit: `ChartFrame` (accessible label + hidden data table; `sr-only` sits on a wrapper div because a `<table>` ignores the 1 px width), `Sparkline`, `KpiCard`/`DeltaChip`, `TrendArea`, `ParetoChart`, `Treemap`, `StackedBars`, `RiskMatrix`, `Waterfall`, `HeatCalendar`, `Gauge`, `RadarChart`, `Timeline`. Numbers drive geometry only; printed values are the API's exact strings. Recharts animation stays off (ISSUES #10). Dates use fixed month names (`MONTHS`, `shortDate`) so server and browser render the same text.
- Tokens added: `--seq-1…5` with `--seq-ink-1…5`, `--div-neg/mid/pos`, `--font-display` (Newsreader). The `--ai` tint and page wash were removed at the owner's request (DEC-028).
- Palette and type pairing (DEC-029, dark planes replaced by DEC-031): dark "Obsidian" = warm charcoal planes, ivory ink, champagne actions; light = navy on ivory; Newsreader for `PageHeader` titles and landing headlines (`font-display`), Inter for everything else.
- `BrandLogo` draws a `--logo-plate` behind the artwork by default (navy `#101a2e` in dark, white in light: each logo file's own background), so the logo is a deliberate tile on any plane; pass `plate={false}` only where the parent already has that colour.

## Testing

Vitest (`tests/unit`: formatters, API client, CSP, provenance, command palette, shortcuts, theme/rail state, `theme-init.js` visibility handling, SSE parsing, selection limits, Analyzable/Lens behaviour) and Playwright (`e2e/`: flows on an isolated production build, including the palette, shortcuts and rail, background-tab and reduced-motion entrances). See `06-operations/TESTING.md`.
