# Test Runs

Every test, lint, type-check or audit run is recorded here: date, step, exact command, result. Failures are recorded too — never deleted.

| Date | Step | Command | Result | Notes |
|---|---|---|---|---|
| 2026-10-27 | M1-2 | spike run 1 (`uv run --no-project … python spike.py`) | FAIL | `ILIKE ESCAPE '\\'` rejected by DuckDB |
| 2026-10-27 | M1-2 | spike run 2 | FAIL | interrupt test hit an aborted transaction from the write test (script bug: missing rollback) |
| 2026-10-27 | M1-2 | spike run 3 | FAIL | script syntax error (edit artifact) |
| 2026-10-27 | M1-2 | spike run 4 | **PASS** | all checks in ADR-0005 |
| 2026-10-27 | M1-3 | `uv run pytest -q` | **27 passed** | config, tenancy, mapping unit tests |
| 2026-10-27 | M1-3 | `uv run ruff check .` | 11 errors → fixed | style/PT018/E501/E741 |
| 2026-10-27 | M1-3 | `uv run mypy` (strict) | 7 errors → fixed → **clean** | SA type map typing |
| 2026-10-27 | M1-3 | `uv run pytest -q` (after fixes) | **27 passed** | |
| 2026-10-27 | M1-4 | `uv run lumiant-synthetic generate --all` | **OK** | alpha 3.8 s, beta 2.1 s |
| 2026-10-27 | M1-4 | `uv run pytest -q` | **43 passed** | +16 synthetic tests (determinism, Σ movements = balances for both schemas, no negative running balances, referential integrity, join-key uniqueness, scenarios, DECIMAL types) |
| 2026-10-27 | M1-4 | `uv run ruff check .` / `uv run mypy` | 20 + 3 findings → fixed → **clean** | |
| 2026-10-27 | M1-5 | `uv run pytest -q -x` | 1 failed | DuckDB same-file config conflict between test raw connection and connector |
| 2026-10-27 | M1-5 | `uv run pytest -q` | 98 passed, **6 failed** | Decimal rounding by SQLAlchemy (real bug), guard parse with pyformat dialect in test, guard reason ordering, test plan shape |
| 2026-10-27 | M1-5 | `uv run pytest -q` | **104 passed** | after fixes |
| 2026-10-27 | M1-5 | `uv run ruff check .` / `uv run mypy` | 13 + 9 findings → fixed → **clean** | |
| 2026-10-27 | M1-6 | `uv run pytest -q` | 127 passed, **6 failed** | SQL guard rejected `AND`/`OR` (sqlglot `Func` subclasses) in metrics gap plan, search and below-reorder |
| 2026-10-27 | M1-6 | `uv run pytest -q` | **133 passed** (2 warnings) | after guard allowlist fix; warnings = Starlette httpx deprecation + 1 related |
| 2026-10-27 | M1-6 | `uv run ruff check .` / `uv run mypy` | 4 findings → fixed → **clean** | |
| 2026-10-27 | M1-7 | `uv run pytest -q tests/unit/test_audit_store.py` | **1 passed** | regression for first-run SQLite dir bug |
| 2026-10-27 | M1-7 | `pnpm typecheck` / `pnpm lint` | **clean** | |
| 2026-10-27 | M1-7 | `pnpm test` (vitest) | 14 passed, **6 failed** → **20 passed** | failures were test env (NBSP in Intl output, missing ResizeObserver in jsdom) |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | 2 passed, **3 failed** | click before router settled; hidden previous route matched locator |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | 3 passed, **2 failed** | duplicate pager locator; options not loaded yet |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | 4 passed, **1 failed** | **real bug**: debounced search overwrote warehouse filter |
| 2026-10-27 | M1-7 | `pnpm exec playwright test` | **5 passed** | after fix; includes `next build` |
| 2026-10-27 | M1-8 | `pnpm run check` (root: ruff, ruff format, mypy, pytest, eslint, tsc, vitest) | **all green**: 134 API passed, 20 web passed | 2 warnings (Starlette httpx deprecation; a test-only Pydantic enum warning, then fixed) |
| 2026-10-27 | M1-8 | `uv run pytest -q` after warning fix | **134 passed**, 1 warning | |
| 2026-10-27 | M1-8 | `pnpm audit` (apps/web) | **0 known vulnerabilities** | |
| 2026-10-27 | M1-8 | `uvx pip-audit -r <exported requirements>` | **0 known vulnerabilities** | first attempt not run: a safety check blocked a temp-file path outside the project; rerun with the scratchpad |
| 2026-10-27 | M2 | `uv run pytest -q` | **177 passed** | +26 costing/ABC hand-computed, +5 item-code, +10 analysis integration tests vs raw SQL |
| 2026-10-27 | M2 | `uv run ruff check .` / `mypy` | clean (E501 exempted in `analyses/risks.py`) | |
| 2026-10-27 | M2 | `pnpm exec playwright test` | **8 passed** | +3: risks, costs, role-hidden nav |
| 2026-10-27 | M3 | `uv run pytest -q` | 219 passed, **1 failed** | model prose overwrote a failed-tool message (real bug) |
| 2026-10-27 | M3 | `uv run pytest -q` | **220 passed** | golden (14), adversarial (8), grounding (4), provider/endpoint tests with a fake Anthropic client |
| 2026-10-27 | M3 | `pnpm exec playwright test` | 9 passed, **1 failed** | ambiguous "Ask" button locator (test bug) → exact match → **11 passed** |
| 2026-10-27 | M4 | `uv run pytest -q` | **234 passed** | +14 report/export tests |
| 2026-10-27 | M4 | `pnpm exec playwright test` | **12 passed** | +2 (guided menu + reports; reduced role) |
