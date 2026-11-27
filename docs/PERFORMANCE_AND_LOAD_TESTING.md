# Performance and Load Testing

_Measured 23 Nov 2026 on the developer laptop (Windows 11, Python 3.13, single process, no other load). Synthetic, deterministic data (seed 42). These are engine timings, not HTTP load tests._

## What was found and fixed

The first benchmark run of the planning engine **did not finish in 10 minutes** at the smallest size. Profiling showed three linear lookups inside hot loops: the planning policy per item, the planned order by id, and the demand entry by id in late-order reasons. BOM selection scanned every BOM for each production order, and calendar arithmetic was recomputed with identical arguments. All were replaced with indexes or caches. The 85 scenario checks and 19 integration tests still pass.

| Change | File |
|---|---|
| Policy index per run | `planning/mrp.py` `_Run._policy` |
| Planned-order and entry indexes | `planning/mrp.py` (`_order_by_id`, `MrpResult.order/entry`) |
| BOMs indexed by parent item | `planning/bom.py` `_by_item` |
| Cached working-day arithmetic (immutable calendar) | `planning/calendar.py` (`lru_cache`) |
| Cheap upper-bound check before text similarity | `planning/duplicates.py` (`quick_ratio`) |

## Results after the fixes

| Workload | Size | Time |
|---|---|---|
| MRP (multi-level, 3 SA + 6 RM per FG, 8 RM per SA) | 100 FG, 300 SA, 2,000 RM, 1,000 order lines, 2 warehouses → 12,642 planned orders | **1.16 s** |
| MRP | 500 FG, 1,500 SA, 10,000 RM, 5,000 order lines, 3 warehouses → 50,315 planned orders | **5.44 s** |
| MRP | 1,000 FG, 3,000 SA, 20,000 RM, 20,000 order lines, 5 warehouses → 213,684 planned orders | **46.6 s** |
| Supplier comparison | 20 offers, 50,000 delivery records | **0.33 s** |
| Duplicate detection | 5,000 items (was 19.2 s before the upper-bound check) | **5.1 s** |
| Duplicate detection | 20,000 items | 128.7 s |

## Limits and honest caveats

- **These numbers exclude data loading.** The planning loader pages raw rows through the query engine (`max_rows` × 20 pages). For millions of stock and movement rows it must aggregate in SQL first (stock per item, warehouse and status; open supply per item and date). That is the next performance task.
- **The largest MRP size is too slow for an interactive request.** Runs of that size should go to a background job (202 + job id) with cached results per data snapshot.
- **Duplicate blocks are capped at 500 items** per block (group plus first word). In very large groups, items beyond the cap are not compared. Finer blocking (normalised token signatures or MinHash) is needed before running on large item masters, and the cap must be reported in the result, not applied silently.
- **No HTTP load test or concurrency test has been run.** A k6 or Locust run against staging (concurrent planners, mixed read load, rate limits on) is still required.
- The query engine's own limits (row caps, timeouts, read-only pooled connections) are unchanged and covered by existing tests.

**Reproduce:** the benchmark script used is `bench_planning.py` (session scratchpad); it builds the synthetic data with a fixed seed and times `run_mrp`, `compare_suppliers` and `find_duplicates`. Adding it to `services/api/benchmarks/` is a follow-up.

## Overview load (V0, 26 Nov 2026)

**Method.** `services/api/benchmarks/overview_load.py` runs the API in-process against a freshly generated full-size
demo-alpha (600 items, about 82,000 movements), signs in as `alpha.admin`, replays the requests a cold Overview sends,
and counts every statement the DuckDB connector executes. Query counts do not depend on the machine; timings are this
Windows laptop. Web bundle sizes come from `apps/web/scripts/bundle-report.mjs` on a production build.

| | Before V0 (TEST_RUNS S10-25) | After V0 (TEST_RUNS S10-28) |
|---|---|---|
| Overview requests | 17 | 16 (the KPI, area board and panel share one below-reorder request) |
| Source queries, cold Overview | 79 | 41 |
| Sum of cold request times | 1,959 ms | 1,184 ms |

What changed: below-reorder runs once per scope instead of five times, the missing-valuation count once instead of
five, and the insight feed reuses the Overview's analyses (`analyses/cache.py`: 60 s, keyed by tenant, scope,
permissions and the data timestamp; never shared across scope). `tests/integration/test_overview_budget.py` fails if a
cold Overview on the test tenant needs more than 45 source queries.

**Budgets still unmet:** landing page first-load JS 193 KB gzip against a 100 KB target (ISSUES #57). LCP and route
change times have not been measured in a browser yet.
