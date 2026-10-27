# Issues, Limitations, Tech Debt

Open items first. Close an item by changing its status and adding the date and fix reference — don't delete it.

| # | Type | Description | Impact | Status | Opened |
|---|---|---|---|---|---|
| 1 | Limitation | No Docker/PostgreSQL/SQL Server/Oracle on the dev machine; only the DuckDB connector can be tested locally | Postgres app DB and customer connectors untested | Open | 2026-10-26 |
| 2 | Tech debt | Conservative pins (TS 5.9, DuckDB 1.5, SQLAlchemy 2.0) need an upgrade review | Upgrade work in M6 | Open | 2026-10-26 |
| 3 | Gap | No value-level mapping yet (e.g. source `ROH` → canonical `RAW`); synthetic writer stores canonical codes | Real customers need value maps (M5) | Open | 2026-10-26 |
| 4 | Gap | No rate limiting until M6 | DoS risk in shared environments | Open | 2026-10-26 |
| 5 | Design note | Datasets without a warehouse key (item master, suppliers, departments) are visible tenant-wide to anyone with `inventory:read` | Customer may require item-level restrictions (Q-011) | Open | 2026-10-27 |
| 6 | Gap | Expensive-query protection is row cap + timeout only; no cost estimation / concurrency limit per tenant | Large customer warehouses (M6) | Open | 2026-10-27 |
| 7 | Fixed | SQLAlchemy Numeric result processing rounded aggregated decimals to the declared scale | Totals off in the 5th+ decimal | **Fixed 2026-10-27** (`ExactDecimal` in `query/compiler.py`, test `test_alpha_value_matches_independent_sql`) | 2026-10-27 |
| 8 | Tech debt | Starlette warns that `httpx` in `TestClient` is deprecated in favour of `httpx2` | Test-only; revisit with dependency upgrades (M6) | Open | 2026-10-27 |
| 9 | Gap | Web app sends X-Frame-Options/nosniff/Referrer-Policy/Permissions-Policy but no Content-Security-Policy yet (Next inline scripts need nonces) | XSS defence-in-depth (React escaping still applies) | Open | 2026-10-27 |
| 10 | Cosmetic | Entrance animations (`.rise`) pause while a tab is in the background, so content can look faded until the tab is shown | None functionally | Open | 2026-10-27 |
| 11 | Fixed | API crashed on first run because migrations ran before the SQLite folder existed | Fresh installs failed | **Fixed 2026-10-27** (`audit/store.py`, `test_audit_store.py`) | 2026-10-27 |
| 12 | Fixed | Inventory search debounce could overwrite a filter chosen during the debounce window | Wrong filters applied | **Fixed 2026-10-27** (`explorer.tsx`, e2e `inventory search, filters and paging`) | 2026-10-27 |
