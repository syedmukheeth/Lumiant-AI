# Feature Catalog

All features — from the brief and the value-adds proposed in session 01 — with priority, milestone, and status.
Priority: **P0** MVP-critical · **P1** strong value · **P2** later.

## Core (from the brief)

| Feature | P | M | Status |
|---|---|---|---|
| Project knowledge base + logs (this folder) | P0 | M1 | **Verified** |
| Tenant config + validation | P0 | M1 | **Verified** |
| Canonical model + mapping layer | P0 | M1 | **Verified** (no value maps yet, ISSUES #3) |
| Synthetic data generator (2 tenants, different schemas) | P0 | M1 | **Verified** |
| Read-only connector (DuckDB synthetic) | P0 | M1 | **Verified** |
| Deterministic query core (plan → validate → compile → guard → execute) | P0 | M1 | **Verified** |
| Dev-only auth + server-side RBAC + warehouse/field scope | P0 | M1 | **Verified** (dev auth only) |
| Audit events | P0 | M1 | **Verified** (writes; explorer UI in M5) |
| Overview dashboard + inventory explorer | P0 | M1 | **Verified (synthetic)** |
| Below-reorder analysis | P0 | M1 | **Verified (synthetic)** |
| Costing engine (MWA, periodic WA, FIFO layers, lot, latest price) | P0 | M2 | Not started |
| ABC computed vs assigned | P0 | M2 | Not started |
| Risk analyses (excess, slow/dormant, ageing, expiry, master-data quality, price movement) | P0 | M2 | Not started |
| Item-code parser | P1 | M2 | Not started |
| AI chat agent | P0 | M3 | Designed |
| Graphical menu of guided analyses | P0 | M4 | Not started |
| Reports + CSV/XLSX export + print | P0 | M4 | Not started |
| Schema discovery + profiling | P1 | M5 | Not started |
| OIDC with customer IdP | P0 | M6 | Blocked (Q-010) |
| Real customer connector | P0 | M7 | Blocked (Q-001–Q-003) |

## Value-adds (proposed session 01, approved with the plan)

| # | Feature | Why | P | M | Status |
|---|---|---|---|---|---|
| V1 | Semantic metric catalog (versioned, rule text, `draft`/`customer-approved`) | Every number traces to a definition shared by dashboard, chat, reports | P0 | M1 seed, M5 admin UI | **Verified** (7 draft metrics; admin UI M5) |
| V2 | "Show your work" provenance card | Trust, audit, reconciliation | P0 | M1 | **Verified** |
| V3 | Currency & UoM safety rails | Prevents silently wrong totals | P0 | M1 | **Verified** |
| V4 | Numeric grounding guard | Stops hallucinated numbers | P0 | M3 | Designed |
| V5 | Editable query chips | Transparency, lower AI cost | P1 | M3/M4 | Designed |
| V6 | Capability readiness matrix | Honest "can't answer", onboarding checklist | P1 | M3, M5 | Designed |
| V7 | Tenant glossary/synonyms | Customer vocabulary without code | P1 | M3 | Designed |
| V8 | Clarification engine | No guessed answers | P1 | M3 | Designed |
| V9 | AI data boundary + disclosure log | Enables AI-provider approval | P0 | M3 | Designed |
| V10 | AI-off mode | Value without LLM approval | P0 | M1 by design | **Verified** (M1 has no AI dependency) |
| V11 | Eval harness (golden + adversarial) | Measurable agent quality | P0 | M3 | Designed |
| V12 | Drill-through from charts/KPIs | "Explain this number" | P1 | M4 | Not started |
| V13 | Mapping studio (AI-suggested, human-approved) | Onboard customers without code | P1 | M5 | Not started |
| V14 | Reconciliation harness vs customer reports | Go-live correctness gate | P0 | M5 | Not started |
| V15 | Scheduled digests & watchlists | Proactive value (recommendations only) | P2 | M7 | Not started |
| V16 | Feedback → eval pipeline | Continuous improvement | P1 | M3/M4 | Not started |
| V17 | Permission-aware result cache | Speed without leaks | P2 | M6 | Not started |

## Explicitly out of scope (unless the customer provides data + approval)

Demand forecasting, invented reorder points/lead times, technology-obsolescence prediction from stock alone, any write-back to source systems, automatic purchasing actions.
