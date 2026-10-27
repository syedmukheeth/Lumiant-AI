# ADR-0002: The LLM never writes SQL or computes authoritative numbers

- **Status:** Accepted
- **Date:** 2026-10-26
- **Session:** S01
- **Related:** brief §10.1, §10.3, §11; REQ-030–REQ-035

## Context
Text-to-SQL by an LLM makes the model part of the security boundary (scope, tenant, sensitive columns, DML) and makes numbers non-deterministic. The brief requires that security be enforced by application code and that the AI not invent financial calculations.

## Decision
- The model may only call typed tools: `query_inventory(QueryPlan)` and named analyses. It never sees physical table names or SQL.
- The application validates plans, injects scope after the model's output, compiles SQL with SQLAlchemy Core (bound parameters), re-checks with a sqlglot guard, and executes on a read-only connection.
- Answers are grounded: numbers in prose must exist in tool results (M3 grounding guard).

## Consequences
- + Security and correctness are independent of model behaviour; fully testable without an LLM.
- + Dashboard, menu, reports and chat share one engine; AI-off mode is natural.
- − Questions outside the plan's expressiveness need a new analysis (deliberate: each one is reviewed and tested).

## Alternatives considered
- LLM-generated SQL + validator: validator must fully understand arbitrary SQL; scope injection into arbitrary SQL is error-prone.
- Semantic-layer products (Cube, dbt SL): extra infrastructure before requirements are known; can be adopted later behind the same plan contract.

## Revisit when
Never for the security property. The plan's expressiveness can grow (new ops, joins) under tests.
