# Query Engine

Status: **Implemented and tested (M1)** under `services/api/src/lumiant/query/`. The code is authoritative if this drifts.

The query engine is the single path to customer data. Dashboard widgets, inventory pages, analyses, the future chat agent and reports all use it.

## 1. QueryPlan (input contract)

```json
{
  "dataset": "stock_balance",
  "dimensions": ["warehouse_id", "warehouse.name"],
  "measures": [{"field": "stock_value", "agg": "sum", "alias": "value"}],
  "filters": [
    {"field": "item.item_group", "op": "in", "value": ["RUBBER", "FLAMMABLE"]},
    {"field": "quantity", "op": "gt", "value": "0"}
  ],
  "having": [{"measure": "value", "op": "gt", "value": "1000"}],
  "order_by": [{"field": "value", "direction": "desc"}],
  "limit": 50,
  "offset": 0
}
```

- `extra="forbid"` everywhere: unknown keys are rejected.
- `dimensions` without `measures` = row listing (non-aggregated); with `measures` = GROUP BY.
- Aggregations: `sum`, `count`, `count_distinct`, `min`, `max`, `avg`.
- Filter ops: `eq`, `ne`, `in`, `not_in`, `lt`, `lte`, `gt`, `gte`, `between`, `is_null`, `is_not_null`, `contains` (case-insensitive substring; wildcard characters escaped).
- Values are JSON scalars/strings; coerced to the field type (decimals from strings to avoid float loss).

## 2. Validator (authoritative rules)

In order; first failure stops the request with a safe error code.

| # | Rule | Error code |
|---|---|---|
| 1 | Dataset exists in canonical catalog **and** is mapped for the tenant | `dataset_not_available` |
| 2 | Every referenced field exists (direct or via an approved join) and is mapped | `field_not_available` |
| 3 | Joined field references only approved join paths | `join_not_allowed` |
| 4 | Sensitive (`cost`) fields used anywhere require `cost:read` | `forbidden_field` |
| 5 | Operator valid for field type (e.g. no `contains` on decimals); `in` lists ≤ 500 values | `invalid_filter` |
| 6 | Value coercion succeeds | `invalid_value` |
| 7 | Aggregation valid for field role/type (no `sum` on strings) | `invalid_aggregation` |
| 8 | Explicit filter on a scope key with values outside the principal's scope | `forbidden_scope` (403) |
| 9 | **Inject** `scope_key IN (allowed)` for the base dataset (unless scope is `*`) | — |
| 10 | **Safety rails**: measures with currency/unit companions → companion added to dimensions | — (warning added) |
| 11 | `limit` defaults to 100, max = tenant policy `max_rows` (default 1000) | `limit_exceeded` if above hard cap |
| 12 | `order_by` references a selected dimension or measure alias | `invalid_order` |

Output: `ValidatedPlan` — immutable, includes the injected filters separately so provenance can show them.

## 3. Compiler

`ValidatedPlan` + tenant mapping → SQLAlchemy Core `Select`:
- physical tables/columns from the mapping (identifiers quoted by SQLAlchemy),
- labels = canonical names (so results are canonical regardless of tenant),
- computed fields expanded from the catalog (e.g. `stock_value = quantity * valuation_price`),
- every value is a **bound parameter**; `contains` uses `ILIKE` with escaped pattern and `ESCAPE '\'`,
- fetch `limit + 1` rows to detect truncation,
- decimal output columns use `ExactDecimal` (no SQLAlchemy result processing): `Numeric(18,4)` processing was found to round aggregates to 4 dp (ISSUES #7),
- `count_only=True` builds `SELECT count(*) FROM (<same filtered query>)` for pagination totals,
- dialect-aware (V0, ISSUES #49): `OFFSET` is emitted only when paging (`offset > 0`), so SQL Server can use `TOP`
  for single-number plans; null ordering is `NULLS LAST` everywhere except SQL Server, which gets a
  `CASE WHEN x IS NULL THEN 1 ELSE 0 END` sort key first. The validator refuses `offset > 0` without an ordering.
  `tests/unit/test_dialect_matrix.py` compiles representative plans for DuckDB, PostgreSQL, SQL Server and Oracle
  and runs each through the guard (compile-only; real engines need the V1 conformance suite).

## 4. SQL guard (defense in depth)

Compiled SQL is parsed with **sqlglot** (dialect of the tenant connector) and rejected unless:
- exactly one statement, and it is a `SELECT`;
- every table referenced is one of the tenant's mapped physical tables;
- no `information_schema`, `pg_catalog`, `sys.`, `duckdb_*` or other system objects;
- no DDL/DML/`COPY`/`ATTACH`/`PRAGMA`/`INSTALL`/`LOAD` nodes,
- every function node is on an allowlist (`AND`, `OR`, `SUM`, `COUNT`, `MIN`, `MAX`, `AVG`, `COALESCE`, `CAST`, `NULLIF`, since M8 `CASE` with its `IF` branches for value maps, and since V0 `LOWER` for `contains` on dialects without `ILIKE`). Window aggregates (`SUM(...) OVER (...)`) pass because `SUM` is allowed; ranking functions (`ROW_NUMBER`, `RANK`, `LAG`) do not. sqlglot models `AND`/`OR` as functions; anything else (`read_csv`, `getenv`, `duckdb_settings()`) is refused,
- the SQL is rendered with the connector's own dialect and `render_postcompile`, so IN-lists are expanded before parsing.

Clients only ever see `query_rejected`; the specific reason goes to server logs and the audit trail.

## 5. Executor + connector

- Connector per tenant (see `CONNECTORS.md`), read-only at the DB level.
- Timeout per tenant policy (`query_timeout_s`, default 15 s). DuckDB has no native statement timeout → a timer calls `connection.interrupt()`.
- Result: `ResultSet{columns[{name,type}], rows, row_count, truncated, duration_ms}`; decimals stay `Decimal`.

## 6. Provenance (generated, never hand-written)

```json
{
  "tenant_id": "demo-alpha",
  "source_system": "Synthetic DuckDB warehouse (demo-alpha)",
  "synthetic": true,
  "dataset": "stock_balance",
  "source_objects": ["ZV_STOCK", "ZV_MATERIAL"],
  "fields": {"stock_value": "ZV_STOCK.LABST * ZV_STOCK.VERPR", "warehouse_id": "ZV_STOCK.WERKS"},
  "filters": {"user": [...], "injected": [{"field": "warehouse_id", "op": "in", "value": ["N100","N200"], "reason": "warehouse_scope"}]},
  "auto_grouped": ["currency"],
  "metric": {"id": "inventory_value_by_warehouse", "version": 1, "status": "draft", "rule": "Σ on-hand quantity × source valuation price, per currency"},
  "data_as_of": "2026-10-25T23:00:00Z",
  "row_count": 6,
  "truncated": false,
  "executed_at": "…",
  "duration_ms": 12,
  "sql": "…only when principal has query:view_sql…"
}
```

## 7. Audit

One `audit_event` per data request (allowed **and** denied): request_id, timestamp, tenant_id, user_id, action (`metric:<id>`, `query`, `inventory.balances`, …), dataset, decision (`allow`/`deny`), reason_code, row_count, duration_ms, status. **No result values, no filter values** (filter *fields* only).

Writes fail closed (DEC-012): each row is committed before the response, and a failed write returns no data. On
SQLite the app database runs WAL with `synchronous=NORMAL` (S11, ADR-0014). Commits still happen per row; only the
fsync per commit goes, so a power cut can lose the last commits but cannot corrupt the file.

## 8. Named analyses

Analyses that need SQL shapes the generic plan cannot express (e.g. below-reorder needs `reorder_policy LEFT JOIN aggregated stock` so zero-stock items appear) are hand-written SQLAlchemy Core queries in `analyses/`, but they **must** use the same building blocks: mapping resolver, scope injection helper, sql_guard, executor, provenance, audit.

Since V0:
- **ABC** is computed in the source with window sums (cumulative share before each item, ties by item id), so it
  has no item cap; it matches `costing.abc.classify` on the full data (`test_scale_limits.py`).
- Analyses that need every row (cost comparison movements and purchases, the item-code check) read them in pages
  of `max_rows` (`risks._paged`, up to 50 pages) and refuse or report `partial` only beyond that.
- Results of below-reorder, excess, dormant, expiry, data quality and the metric gap count are shared for 60 s
  between callers with the same tenant, warehouse scope, permissions and data timestamp (`analyses/cache.py`);
  hits are audited with reason `cache`; the insight feed's `fresh=true` bypasses it.
- Since S11 (ADR-0014) the same cache also shares:
  - catalog metrics (audited as `analysis:metric:<id>` on a hit)
  - the inventory filter lists
  - ABC, cost comparison and value concentration
  - the planning load (`planning_load`, keyed by planning date), so master data, planning, suppliers, commitments
    and lifecycle read the source once per scope per minute
  - duplicate findings

  A caller without the permission is refused before the cache is read. The capability's own audit row (for example
  `planning:duplicates`) is still written on every call. Tests: `test_result_cache.py`.
