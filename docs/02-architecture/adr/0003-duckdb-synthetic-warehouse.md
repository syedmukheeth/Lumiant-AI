# ADR-0003: DuckDB files as the synthetic customer warehouse

- **Status:** Accepted (driver combination confirmed by the M1-step-2 spike, see ADR-0005)
- **Date:** 2026-10-26
- **Session:** S01
- **Related:** F-005, F-007; REQ-005; ADR-0005

## Context
We need a realistic stand-in for a customer warehouse to develop and test against. The dev machine has no Docker, PostgreSQL, SQL Server or Oracle. Money and quantities need true DECIMAL semantics; the stand-in should enforce read-only at the database level like a real read-only service account.

## Decision
- Each synthetic tenant is a **DuckDB file** generated deterministically by `lumiant.synthetic` into `services/api/data/synthetic/` (gitignored, regenerable).
- The API opens these files with `read_only=True`.
- Physical table/column names differ per tenant (SAP-style vs snake_case) to exercise the mapping layer.

## Consequences
- + Real `DECIMAL(18,4)`, fast analytics, zero install, DB-level read-only.
- + Two different physical schemas prove mapping and tenant isolation.
- − DuckDB is not a customer technology; passing tests here says nothing about MSSQL/Oracle/Postgres behaviour (stated in `CONNECTORS.md`).
- − No native statement timeout → timer + `interrupt()`.

## Alternatives considered
- SQLite: no DECIMAL type (floats) → unacceptable for money aggregation.
- Embedded PostgreSQL wheels: extra moving parts on Windows; revisit if a Postgres customer appears.
- CSV/Parquet + pandas: not a SQL warehouse; would bypass the compiler.

## Revisit when
Docker or a Postgres test instance becomes available (add Postgres synthetic warehouse), or a customer DB technology is confirmed.
