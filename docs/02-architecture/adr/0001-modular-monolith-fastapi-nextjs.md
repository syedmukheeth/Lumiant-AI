# ADR-0001: Modular monolith — FastAPI backend + Next.js frontend

- **Status:** Accepted
- **Date:** 2026-10-26
- **Session:** S01
- **Related:** brief §4; REQ-001, REQ-020, REQ-034; F-007

## Context
The hardest parts of the product are enterprise database connectivity, deterministic financial calculations, and safe AI orchestration. The brief prefers Next.js for the UI, asks us to evaluate FastAPI vs Next.js server APIs, and warns against unnecessary microservices.

## Decision
- One Python **FastAPI** service (`services/api`) owns data access, authorization, query engine, calculations, audit and (M3) AI orchestration, organised as internal modules.
- One **Next.js** app (`apps/web`) owns the UI and proxies `/api/*` to FastAPI (same-origin cookies, no CORS).
- No other services.

## Consequences
- + Best driver ecosystem (python-oracledb, mssql-python/pyodbc, psycopg 3, hdbcli), SQLAlchemy Core for dialect-correct parameterized SQL, `Decimal`, sqlglot.
- + Single place where security is enforced.
- − Two languages/toolchains (pnpm + uv). Mitigated by root scripts and docs.
- − Types are not shared automatically across the boundary; zod schemas on the web side mirror API models (OpenAPI codegen can be added later).

## Alternatives considered
- **Next.js-only (route handlers)**: weaker enterprise DB drivers in Node (Oracle/MSSQL/HANA), no SQLAlchemy-equivalent dialect compiler; financial decimals less ergonomic.
- **Microservices (query svc, calc svc, ai svc)**: operational cost with no current scaling need.

## Revisit when
A component needs independent scaling or deployment cadence (e.g. heavy report generation → background worker).
