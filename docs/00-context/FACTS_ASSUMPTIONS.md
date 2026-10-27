# Facts, Assumptions, Unknowns

The master prompt forbids inventing requirements. This ledger keeps the three categories strictly apart.
Every item has an ID so code comments, ADRs and logs can cite it.

- **F-** Confirmed fact (with source).
- **A-** Assumption we are working under (with why, and what would change if wrong).
- **U-** Unknown — must be answered by the customer/Lumiant (linked to `07-customer/OPEN_QUESTIONS.md`).
- **D-** Decision requiring customer approval before production.

---

## Confirmed facts

| ID | Fact | Source |
|---|---|---|
| F-001 | Product is for Lumiant Group, to be deployed for multiple customers. | Master prompt §1, §15 |
| F-002 | The working directory `E:\LUMIANT AI` was empty and not a git repository on 2026-10-26. | Session 01 investigation (`ls -la`, `git status`) |
| F-003 | The AI must not access operational production DBs; only an approved data warehouse via read-only access. | Master prompt §5, §5.4 |
| F-004 | Customer DB technology, schema, IdP, hosting, AI provider and authorization policies are **not yet known**. | Master prompt §3.2 |
| F-005 | Synthetic data only until approved customer data is available; must be labelled. | Master prompt §3.2, §21 |
| F-006 | Preferred frontend: Next.js + React + TypeScript + Tailwind + accessible components + charting library. | Master prompt §4 |
| F-007 | Dev machine: Windows 11, Node 22.20, pnpm 11.10, uv 0.11.15 with CPython 3.13.13/3.12.13, git 2.50, Java 24; **no** Docker, WSL, PostgreSQL, SQL Server or Oracle tools; 8 logical CPUs, 7.8 GB RAM. | Session 01 commands (see `ENVIRONMENT.md`) |
| F-008 | Roles listed in the brief (super admin, department admin, standard user) are explicitly **not final**. | Master prompt §14 |
| F-009 | LIFO must not be applied to accounting valuation automatically; costing rules need customer approval. | Master prompt §9.2 |
| F-010 | Repo owner wants every piece of project knowledge, flow and log kept as Markdown in the repo. | User instruction, session 01 |

## Working assumptions

| ID | Assumption | Why | If wrong |
|---|---|---|---|
| A-001 | The customer can expose inventory data through SQL-queryable views/tables in a warehouse reachable from the deployment network. | Brief's default architecture | Need file/API-based ingestion connector instead. |
| A-002 | A read-only service account can be provisioned. | Brief §5.4 | Cannot go live; DB-level enforcement is a hard requirement. |
| A-003 | Stock balances, item master, lots, transactions and purchasing exist as separate (or separable) datasets. | Typical ERP warehouse design | Mapping layer supports computed/derived datasets; may need customer-built views. |
| A-004 | Monetary values come with an explicit currency field or a known single currency per dataset. | Required for safe aggregation | Must configure a fixed currency per mapping; flagged in provenance. |
| A-005 | A valuation price (e.g. moving average) is available from the ERP for inventory value; our own costing engine (M2) reconciles against it. | Avoids inventing valuation | Inventory-value KPI disabled until a costing rule is approved. |
| A-006 | Deployment is likely private (customer-controlled or private cloud); public hosting not assumed. | Brief §4 Deployment | Docs already treat hosting as configurable. |
| A-007 | Single-tenant-per-deployment is acceptable initially; code keeps tenant isolation so shared hosting stays possible. | Brief §15 ("don't build complicated multitenancy first") | Shared multi-tenant hosting needs per-tenant secrets + stronger infra isolation review. |
| A-008 | Python backend is acceptable in customer environments (container or VM). | Common in enterprise | Would need packaging review; no code assumption beyond container. |
| A-009 | Demo currencies USD (alpha) and EUR/GBP (beta) are illustrative only. | Synthetic data | None — synthetic. |

## Unknowns (→ `07-customer/OPEN_QUESTIONS.md`)

| ID | Unknown | Question |
|---|---|---|
| U-001 | Data warehouse product/version and access path | Q-001 |
| U-002 | Source schema (item, stock, lot, transaction, purchasing, costing) | Q-003 |
| U-003 | Identity provider and group→role mapping | Q-010 |
| U-004 | Hosting / network / region constraints | Q-012 |
| U-005 | Approved AI provider and data-handling terms | Q-013 |
| U-006 | Costing policy (moving vs periodic WA, FIFO/LIFO operational rules, latest-price definition, rounding, FX) | Q-006 – Q-008 |
| U-007 | ABC method or authoritative assigned field | Q-005 |
| U-008 | Item-coding rules per customer | Q-004 |
| U-009 | Department ↔ warehouse hierarchy and permission policy | Q-011 |
| U-010 | Audit retention period | Q-014 |
| U-011 | Data volumes and freshness SLA | Q-016 |

## Decisions requiring customer approval before production

| ID | Decision | Status |
|---|---|---|
| D-001 | Which data warehouse objects (views) are approved for the platform | Pending (Q-002) |
| D-002 | Costing / valuation rules used in calculations | Pending (Q-006–Q-008) |
| D-003 | Whether an external AI provider may receive aggregated inventory data | Pending (Q-013) |
| D-004 | Role definitions and permission matrix | Pending (Q-010, Q-011) |
| D-005 | Hosting platform and network topology | Pending (Q-012) |
| D-006 | Audit and data retention periods | Pending (Q-014) |
| D-007 | Metric definitions marked `customer-approved` in the metric catalog | Pending (per metric) |

## Facts added during M1 (session 01)

| ID | Fact | Source |
|---|---|---|
| F-011 | M1 functionality is verified **only** on synthetic DuckDB data with development authentication. | `logs/TEST_RUNS.md`, `00-context/CURRENT_STATE.md` |
| F-012 | SQLAlchemy 2.0 `Numeric(18,4)` result processing rounds aggregated decimals; the query engine bypasses it (`ExactDecimal`). | ISSUES #7, `test_alpha_value_matches_independent_sql` |
| F-013 | DuckDB allows several read-only connections to one file in a process only with identical configuration. | WORKLOG M1-step-5 |

## Assumptions added during M1

| ID | Assumption | Why | If wrong |
|---|---|---|---|
| A-010 | Item master, supplier and department data may be visible to every user of a tenant (only warehouse-keyed data is scoped). | No customer policy yet | Add item-level/department data restrictions (ISSUES #5, Q-011) |
| A-011 | A reorder level is expressed in the item's base unit of measure. | Typical ERP behaviour | Below-reorder must convert or compare per UoM (lines in other units are already excluded and reported) |
