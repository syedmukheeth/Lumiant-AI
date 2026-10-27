# Frontend

Status: **Implemented and tested (M1)**. Code in `apps/web/`: Next.js 16.4 App Router (with `cacheComponents` and `partialPrefetching`), React 19.3, TypeScript 5.9, Tailwind 4 (Turbopack loader), React Query 5.104, Recharts 3.10, Radix popover, lucide icons.

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
- Pages are client components; no server component reads cookies, so Cache Components never needs request data and the API stays the only enforcement point.
- `usePageMe()` reads the session only after hydration (the shell may resolve it first), which prevents hydration mismatches.
- The shell always renders page content (Next 16 instant-navigation validation requires it); the session state only affects the chrome.
- Next keeps the previous route mounted but hidden (React Activity): tests must scope locators to visible regions.

## Components

| Component | Notes |
|---|---|
| `shell/AppShell` | sidebar nav (permission-filtered), user card with roles and scope, header with tenant, **SYNTHETIC DEMO DATA** tape, data as-of (turns orange when stale), theme toggle, sign out |
| `overview/KpiStrip` | inventory value per currency (never summed), items in stock, stock lines, below-reorder count + pairs without policy; locked state for no-cost roles |
| `data/ValueBars` | Recharts horizontal bars for a value metric; currency switcher when >1 currency; excluded-lines note in subtitle |
| `overview/BelowReorderPanel` | lowest coverage first, coverage bar, shortfall, paging |
| `inventory/InventoryExplorer` | URL-state filters, debounced search, server sort + paging, cost columns only with `cost:read` |
| `data/ProvenanceButton` | "provenance slip": source, objects, canonical ← physical fields, user filters, access scope applied by permissions, split-by, rule + status, as-of, rows/duration, SQL (only if the API sent it) |
| `data/Panel`, `ErrorState`, `Skeleton`, `Warnings`, `Pager` | shared frame and states: loading, empty, error (message + request ref), forbidden |

## Formatting

Decimal strings formatted with `Intl.NumberFormat` (string input preserves precision). Currency always shown with its code. Quantities shown with UoM.

## Design tokens

"Ledger" theme in `src/app/globals.css`: warm paper (light) and graphite (dark) with a faint grid; one data accent (teal) and one signal accent (orange) reserved for things that need attention; hazard-tape SYNTHETIC badge. Tokens are CSS variables mapped through Tailwind v4 `@theme inline`. The theme follows the OS and can be toggled (saved in `localStorage`, applied before first paint by a static inline script). Typography: Archivo for UI and IBM Plex Mono with tabular, slashed-zero figures for every number. Entrance motion is a short staggered rise, disabled under `prefers-reduced-motion`.

## Testing

Vitest (`tests/unit`: formatters, API client, provenance) and Playwright (`e2e/`: 5 flows on an isolated production build). See `06-operations/TESTING.md`.
