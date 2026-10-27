# ADR-0005: Conservative version pins for very fresh majors

- **Status:** Accepted (spike result recorded below once run)
- **Date:** 2026-10-26
- **Session:** S01
- **Related:** `00-context/ENVIRONMENT.md`

## Context
Registry check on 2026-10-26 found: TypeScript `latest` = 7.0.2 (Go-native rewrite), DuckDB 2.0.0 released 2026-10-21, SQLAlchemy 2.1.x (2.1.0 on 2026-09-24) while `duckdb-engine` 0.17.0 dates from 2025-03.

## Decision
- TypeScript **5.9.3** for the web app.
- DuckDB **1.5.x**.
- SQLAlchemy **2.0.x** if `duckdb-engine` is required; spike decides.
- Everything else: current stable.

## Consequences
- + Lower risk of toolchain incompatibilities blocking M1.
- − Upgrade work later (tracked in `logs/ISSUES.md`).

## Spike result (2026-10-27, S01, M1-step-2) — **PASS**
Versions: Python 3.13.13, duckdb 1.5.6, duckdb-engine 0.17.0, SQLAlchemy 2.0.55, sqlglot 30.25.0.

| Check | Result |
|---|---|
| SQLAlchemy Core `select` with group/order/limit/IN compiles for DuckDB with bound params (`$n`) | ✅ |
| `DECIMAL(18,4)` results come back as Python `Decimal` | ✅ |
| `connect_args={"read_only": True}` blocks `INSERT` (`InvalidInputException`) | ✅ |
| `driver_connection.interrupt()` from a timer stops a long query after 0.5 s (`InterruptException`) | ✅ — connection needs `rollback()` before reuse |
| `ILIKE … ESCAPE '\'` | ❌ PG dialect renders `'\\'`, DuckDB rejects → **use `!` as escape char** |
| `compile_kwargs={"render_postcompile": True}` expands IN-lists for the guard; sqlglot parses it as one `Select` with table `ZV_STOCK` | ✅ |
| Path containing a space | ✅ |

Decision confirmed: **duckdb 1.5.x, duckdb-engine 0.17.0, SQLAlchemy 2.0.x**.

## Revisit when
M6 hardening, or when Next.js officially documents TS 7 support / duckdb-engine supports DuckDB 2 + SA 2.1.
