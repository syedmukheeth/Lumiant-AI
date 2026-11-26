# Connectors

## Interface (M1)

```python
class Connector(Protocol):
    dialect_name: str                      # sqlalchemy/sqlglot dialect used for compile + guard
    @property
    def dialect(self) -> Dialect: ...  # used to render SQL for the guard
    def health(self) -> bool: ...            # never raises, never leaks details
    def list_objects(self) -> list[ObjectInfo]: ...          # tables/views visible to the account
    def describe(self, schema: str | None, name: str) -> list[ColumnInfo]: ...   # columns + types
    def has_table(self, schema: str | None, name: str) -> bool: ...
    def execute(self, stmt: Select, *, fetch_limit: int, timeout_s: float) -> RawResult: ...
    def dispose(self) -> None: ...
```

- `execute` accepts only a SQLAlchemy `Select` built by the compiler/analyses — there is no `execute(sql_string)` entry point.
- Schema-change detection (M5): compare `describe()` output with the mapping's expected columns/types; report drift.

## Support matrix (truth table — only "Tested" may be called supported)

| Technology | Driver | Status | Evidence |
|---|---|---|---|
| DuckDB file (synthetic demo warehouse) | `duckdb` 1.5.6 + `duckdb-engine` 0.17.0 | **Tested**: read-only, timeout, missing file | `test_query_service.py::test_database_level_read_only`, `::test_timeout_interrupts_long_queries`, `::test_missing_source_is_reported_safely` |
| PostgreSQL | psycopg 3 (`uv sync --extra postgres`) via `SqlConnector` | **Implemented (V1); conformance suite runs in CI** (`api-postgres-redis` job, exact figure equality with DuckDB, read-only session, server-side `statement_timeout`) | `tests/integration/test_sql_connector.py` (PostgreSQL parameter) |
| Microsoft SQL Server | pyodbc + ODBC Driver 18 via `SqlConnector` | **Compiles and passes the guard** (`test_dialect_matrix.py`); not run against a real engine yet (driver not installed by default) | — |
| Oracle Database | python-oracledb (thin mode) via `SqlConnector` | **Compiles and passes the guard**; not run against a real engine yet | — |
| SAP HANA / SAP-related sources | hdbcli + sqlalchemy-hana, or customer-exported views | **Not implemented** — blocked on Q-001 | — |
| Snowflake / BigQuery / Databricks / Fabric | vendor drivers | **Not implemented** — only if customer uses them | — |

| SQLite (development stand-in only) | stdlib `sqlite3` via `SqlConnector`, `mode=ro` | **Tested** on every run: same figures as DuckDB (money to 4 dp: SQLite stores REAL), read-only, timeout, safe failure | `tests/integration/test_sql_connector.py` |

### V1: generic SQL connector and the Connect step

- `connectors/sql_connector.py`: one read-only connector for every SQLAlchemy backend in `GUARD_DIALECTS`; same
  contract as DuckDB (Select only, row cap, client cancel + PostgreSQL `statement_timeout`); floats never leave it.
- Tenant config: `connection: {type: sql, secret_ref: env:NAME}`; the URL (with credentials) lives only in that
  environment variable. A missing variable makes the source `source_unavailable` (503), never a crash.
- `connectors/probe.py` + `POST /api/admin/source/test`: tests a URL once (connect, privilege check, catalog list),
  never stores, logs or returns it. Admin › Data source shows the current source and runs this test.
- `lumiant-synthetic copy --tenant demo-alpha --to <url>` loads a generated warehouse into any engine for demos and
  conformance tests (writes; never against a customer system).

## Read-only enforcement per technology (to apply in M7)

| Technology | DB-level read-only |
|---|---|
| DuckDB | `duckdb.connect(path, read_only=True)` |
| PostgreSQL | dedicated role with `SELECT` on approved views only; `default_transaction_read_only=on` |
| SQL Server | login mapped to user with `db_datareader` on approved schema only (or SELECT on views); `ApplicationIntent=ReadOnly` for AG replicas |
| Oracle | user with `SELECT` grants on approved views only; no `CREATE SESSION` beyond need |
| SAP HANA | technical user with SELECT on calculation/SQL views only |

Application read-only checks (compiler + sql_guard) are **in addition to**, never instead of, DB permissions.

## Adding a connector (checklist)

1. Confirm customer technology, version and approved access path (Q-001/Q-002).
2. Implement class + dialect registration; secrets via `secret_ref` only.
3. Integration tests against an approved **test** environment (never production).
4. Verify read-only at DB level (attempt a write in tests; expect failure).
5. Verify timeouts, row caps, type normalization (DECIMAL → Decimal, dates, NULLs).
6. Update this matrix with evidence links; only then call it supported.
