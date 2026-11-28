# ADR-0014: Client navigation cache, full prefetch and wider shared results

- **Status:** Accepted (owner approved the speed plan, 2026-11-27)
- **Date:** 2026-11-28
- **Session:** S11
- **Related:** ADR-0007 (nonce CSP), DEC-032 (shared analysis cache), DEC-039

## Context
The owner: "the lag and slowness is giving unpolished work … super smooth navigation, fast load". Measured on
production (bom1, demo-alpha admin, 2026-11-27):

| What | Before | Cause |
|---|---|---|
| Rail click, first visit | ~400 ms before anything changed | The root layout reads the request (nonce, ADR-0007), so every route renders per request. Without `loading.tsx`, Next's default prefetch fetched nothing, and a click waited for a server render plus the route's chunks |
| Rail click, revisit | ~110 ms | `staleTimes.dynamic` defaults to 0: the page was fetched again |
| Inventory filter, sort, page | a server round trip each | `router.replace(?qs)` |
| Overview reload | data done at ~1.2 s, 17 API calls in three waves | the shell waited for `/api/auth/me`, the widgets waited for the metric list |
| JS on every page | zod (~30 KB) only to read error bodies; palette, Analyst dock and Recharts loaded up front | |
| Master data | `/api/planning/duplicates` 1.45 s warm | up to ten governed reads per request, uncached; one SQLite fsync per audit row |
| Motion | panels faded in over 420 ms, staggered up to 400 ms, plus a 220 ms route fade | content kept moving for ~0.8 s after it was ready |

The nonce CSP is a security control and stays. Static rendering, Partial Prerendering and `cacheComponents` are
not compatible with a per-request nonce (ADR-0007).

## Decision
1. **Navigation works from a client cache, around the nonce CSP.**
   - `experimental.staleTimes: { dynamic: 30, static: 300 }`.
   - Rail links, the logo and Settings use `prefetch={true}` (a full prefetch, kept for `static` = 5 minutes).
     Once the browser is idle, the shell calls `router.prefetch` for every route the role can open, plus Settings,
     so the palette and G-key jumps are instant too. It also loads the palette and Analyst dock chunks then.
   - `(app)/loading.tsx` is a skeleton of the page header and panels, for any route that was not prefetched.
   - The rail highlight moves on click. The pending link is cleared when the pathname changes.
   - Prefetched payloads are the pages' client shells: no data and no user facts (pages fetch data from `/api`,
     which authorizes every request). The HTML document, with its nonce, is still rendered once per full load.
2. **Data arrives with the page.**
   - One set of query definitions (`lib/queries.ts`) serves the pages and the prefetcher (`lib/prefetch.ts`). A
     pointer over or focus on a rail link prefetches that page's first requests, using the same React Query keys.
   - `me` and `meta` are kept in this tab's `sessionStorage` (display and routing facts only: no token, no rows) and
     restored as stale data, so a reload paints the shell at once while `/api/auth/me` is still asked. A 401,
     sign-out or removal clears the copy. After sign-in, the login response seeds `me`, and `meta` and the metric
     list are prefetched before the redirect.
   - The shell asks for the metric list alongside the session instead of after it.
3. **Filters change the URL without a server trip:** `window.history.replaceState` (Next 16 syncs it with
   `useSearchParams`) in the Inventory explorer, saved views and Commitments.
4. **A lighter, calmer shell.**
   - The error envelope is read by a small type guard instead of zod.
   - The palette, the Analyst dock and the Overview charts load with `next/dynamic` on first use.
   - The Analyst store has `useAnalystSelector`, so streamed steps no longer re-render the shell and every panel.
   - Entrances take 200 ms with 4 px of travel, and staggers stop at 120 ms. The route fade is 140 ms. The skeleton
     shimmer is a `transform` on a pseudo-element, so it is composited, not repainted.
   - Long master-data and planning lists show 100 rows, with "Show more". Geist Mono (identifiers only) is not
     preloaded.
5. **The API shares more results** with the DEC-032 cache, under the same rules:
   - the key holds tenant, scope, permissions and data timestamp
   - every hit writes an audit row (reason `cache`), and errors are never stored
   - a caller without the permission is refused before the cache is read

   Newly shared:
   - catalog metrics
   - inventory filter lists
   - ABC, cost comparison and value concentration
   - the planning load, which serves master data, planning, suppliers, commitments and lifecycle
   - duplicate findings

   The SQLite app database adds `synchronous=NORMAL` to WAL. Every audit row is still committed before the
   response, and a failed write still fails closed; only the per-commit fsync goes.
6. **Cold start:** openpyxl is imported only for an Excel export, tenant YAML uses libyaml's safe loader, and the
   API logs its startup time once per instance.

## Alternatives considered
- **Drop the nonce CSP or render pages statically:** rejected, it is a security control (ADR-0007).
- **A batch Overview endpoint:** not needed now. Shared results and prefetch remove the waves without changing the
  API contract (as DEC-032 found).
- **Server paging for duplicates:** deferred. The cached response answers in about 1 ms warm, and the UI renders 100
  rows at a time. The payload is still the full list (ISSUES #72).
- **A keep-warm schedule:** not possible to any useful effect on the current plan. Hobby schedules run at most every
  15 minutes with 15 minutes of jitter, longer than an idle instance lives (ISSUES #71).

## Consequences
- A page shell can be up to 30 s (revisit) or 5 minutes (prefetched) old on the client. Data freshness is unchanged:
  it is governed by React Query, and by the 60 s result cache within one data timestamp (DEC-032).
- After sign-out the router cache still holds the previous user's page shells. They carry no data, the shell does
  not mount a page outside the next user's sections, and the API refuses its requests (e2e: direct URL, LA-39).
- On SQLite, a power cut can lose the last few audit commits; it cannot corrupt the file. Hosted production uses
  SQLite in `/tmp`, which is lost on every instance recycle anyway. A lasting deployment uses PostgreSQL.
- e2e `navigation.spec.ts` fails if a rail click needs the server again, or if a filter change triggers a page
  request. `scripts/nav-timing.mjs` measures a running deployment; its numbers go in TEST_RUNS.
