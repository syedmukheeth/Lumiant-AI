# Project Assessment (Phase 1) — answers A–J

Written 2026-10-26 (session 01) after investigating the repository and toolchain, before any code was written.
Approved by the repo owner the same day (plan approval in session 01).

---

## A. What was discovered

- `E:\LUMIANT AI` was **completely empty**: no files, no hidden files, not a git repository (F-002).
- Toolchain available: Node 22.20 + pnpm 11.10; Python 3.13/3.12 only via uv 0.11.15; git 2.50; Java 24 (F-007).
- **No Docker, WSL, PostgreSQL, SQL Server or Oracle tooling** → no local enterprise DB can be stood up for integration tests on this machine.
- Registry check of current versions revealed several *very fresh* majors that are risky to adopt today: TypeScript 7.0 (Go-native port), DuckDB 2.0.0 (5 days old), SQLAlchemy 2.1 (1 month old) while the DuckDB SQLAlchemy dialect (`duckdb-engine` 0.17) has not been released since March 2025. See `ENVIRONMENT.md` and ADR-0005.

## B. What already exists

Nothing in the repository. No reusable code, tests, configuration or documentation. This is a **greenfield** project.

## C. What is missing (everything), grouped

| Area | Missing |
|---|---|
| Customer inputs | Warehouse technology, schema, IdP, hosting, AI provider approval, costing policy, ABC method, coding rules, permission policy (see `07-customer/OPEN_QUESTIONS.md`) |
| Product | All application code, synthetic data, tests, docs (this knowledge base is the first artifact) |
| Infrastructure | No container runtime locally; no CI; no deployment target |

## D. Proposed architecture and why it fits

**Modular monolith with two deployables**: a Python **FastAPI** service (`services/api`) that owns all data access, authorization, calculations and (later) AI orchestration, and a **Next.js** web app (`apps/web`) that owns the UI and proxies `/api/*` to FastAPI.

Why:
1. **Data connectivity is the hardest part** and Python has the strongest enterprise driver ecosystem (python-oracledb thin mode, Microsoft's mssql-python / pyodbc, psycopg 3, SAP HANA `hdbcli`) and **SQLAlchemy Core**, which generates parameterized, dialect-correct SQL for MSSQL/Oracle/PostgreSQL from one plan.
2. **Financial correctness**: Python `Decimal` end-to-end; deterministic calculation modules are easy to unit-test.
3. **AI safety**: the LLM produces a typed plan; Python validates it, injects scope, compiles SQL, guards it with **sqlglot**, executes read-only. The LLM never writes SQL (ADR-0002).
4. **No microservices**: one backend process, clear internal modules (`auth`, `tenancy`, `canonical`, `mapping`, `connectors`, `query`, `analyses`, `metrics`, `audit`, `api`). Splitting later is possible along these seams.
5. **Multi-customer by configuration**: tenant YAML (connection ref, mapping, roles, policies) validated at startup (ADR-0006); per-tenant connector engines make cross-tenant access structurally impossible.

Full detail: `02-architecture/ARCHITECTURE.md`.

## E. Recommended stack and trade-offs

| Layer | Choice | Trade-off |
|---|---|---|
| UI | Next.js 16 App Router, React 19, TypeScript 5.9, Tailwind 4, Radix primitives, Recharts 3, React Query 5 | Two languages in the repo (TS + Python); accepted for driver/calculation strengths |
| API | FastAPI + Pydantic 2, sync SQLAlchemy 2.0 Core | Sync endpoints use the threadpool; fine for read-heavy analytic workloads; async drivers are not uniformly available for enterprise DBs |
| SQL generation | SQLAlchemy Core compiler + sqlglot guard | Two SQL libraries, but each does one job (generate vs verify) |
| Synthetic warehouse | DuckDB 1.5 files, opened read-only | Not a customer DB technology; it is a stand-in with real DECIMAL types and real read-only enforcement |
| App metadata DB | SQLite (dev) → PostgreSQL (prod) via SQLAlchemy + Alembic | Postgres path cannot be tested locally until Docker or a Postgres instance is available |
| Auth | Dev-only signed-cookie mode now; OIDC once IdP is known | Dev mode must never reach production → hard startup guard + test |
| AI (M3) | Provider abstraction (Anthropic API / Bedrock / Vertex / Azure OpenAI / self-hosted) | Provider choice blocked on customer approval (Q-013) |

## F. First milestone recommended (approved)

**M1 — Foundation + synthetic data + canonical model + first dashboard**, with the deterministic query core (QueryPlan → validator → compiler → guard → read-only connector → provenance → audit) and server-side RBAC, but **no LLM yet**. Rationale: the dashboard, the graphical menu and the future AI agent all consume the same secured query core, so it must exist and be tested first. Detail: `05-plan/MILESTONE_01.md`.

## G. Exact information needed from the customer

See `07-customer/OPEN_QUESTIONS.md` (Q-001 … Q-017). Highest priority: Q-001 warehouse technology & access path, Q-002 approved views, Q-003 schema documentation, Q-006–Q-008 costing policy, Q-010 identity provider, Q-012 hosting, Q-013 AI provider approval.

## H. Main security and data-correctness risks

See `03-security/THREAT_MODEL.md` and `01-product/AGENT_DESIGN.md`. Top risks:
1. Authorization bypass through the AI path → scope injected by code after the plan is produced; the LLM has no SQL capability.
2. Cross-tenant leakage → tenant only from token; per-tenant engines; tests.
3. Silently wrong totals (mixed currencies/UoMs, wrong mapping, stale data) → safety rails, provenance, as-of display, independent-SQL tests, reconciliation gate.
4. Costing method mismatch with the ERP → costing rules require customer approval; reconcile before production.
5. Prompt injection from data (item descriptions, supplier notes) → treated as data; planted test cases.
6. Dev authentication reaching production → startup guard + test.
7. Unproven connectors claimed as supported → support matrix in `02-architecture/CONNECTORS.md` lists only tested connectors.

## I. Implementation plan ordered by dependency

`05-plan/ROADMAP.md` (M1 → M7) and `05-plan/IMPLEMENTATION_PLAN.md` (checkboxes).

## J. Commands and tests to verify the initial setup

`06-operations/DEV_SETUP.md` and `06-operations/TESTING.md`. Summary:
```bash
cd services/api && uv sync && uv run lumiant-synthetic generate --all
uv run pytest && uv run ruff check . && uv run mypy src
cd apps/web && pnpm install && pnpm lint && pnpm typecheck && pnpm test && pnpm e2e
```
