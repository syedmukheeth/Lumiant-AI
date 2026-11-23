# Master Enterprise Architecture

Lumiant is a **modular monolith** (ADR-0001): one FastAPI service and one Next.js web app, with modules separated in code rather than split into services. This keeps the product deployable on one small host or inside a customer's network, and leaves room to split later if measurements show the need.

```
 ERP / warehouse (read-only)          Lumiant API (services/api/src/lumiant)                       Web (apps/web)
 ─────────────────────────           ─────────────────────────────────────────────────────         ─────────────────
 DuckDB, SAP list exports  ──► connectors ─► mapping (tenant YAML → canonical model)                Monitor: Overview,
 (future: SQL, ERP APIs)                       │                                                   Explore
                                               ▼                                                   Analyze: Inventory,
                              query engine: plan → validator (scope, cost, units, currency)         Risks, Costs, Assistant
                                            → compiler → SQL guard → read-only connector            Plan: Orders & materials
                                            → provenance + audit                                    Procure: Supplier comparison
                                               │                                                   Govern: Item master,
            ┌──────────────┬───────────────────┼───────────────────┬─────────────────┐              Reports, Admin
            ▼              ▼                   ▼                   ▼                 ▼
       metrics,       analyses, costing   planning/ (loader → BOM, MRP,     insights      agent (rules or
       reports        (risks, ABC)        suppliers, transfers, duplicates,              approved LLM) → typed tools
                                          lifecycle, scenario assessor)                  → grounding check
                                               │
                                               ▼
                              JSON (Decimal as string) ─► /api/*  ◄── same-origin rewrite ── browser
```

## Principles

- **The LLM never writes SQL or produces authoritative numbers** (ADR-0002). Every figure comes from the query engine or the planning engine, and the grounding check withholds any answer with an untraced number.
- **Authorization is server-side.** Tenant from the session; warehouse scope injected by the validator; cost fields need `cost:read`. Navigation mirrors this (sections from `/api/auth/me`), but hiding a page is never the control.
- **Read-only and recommendation-only.** No ERP writes, no automatic purchase orders, merges, disposals or substitutions.
- **One engine, many surfaces.** The planning service is shared by the API, the assistant tools and the web pages, so there is no duplicated business logic (`planning/service.py`).
- **ERP-neutral canonical model.** Customer schemas map to it in YAML. Source identifiers and physical names stay in provenance, and new datasets are optional, so existing tenants keep working.
- **Honest gaps.** A missing dataset returns 409 "Needs more data". Unknown lead times are `None`, not 0. Unsupported scenarios are reported by `scenario.assess()` and audited as capability gaps.

## Module responsibilities (where to look)

| Concern | Module |
|---|---|
| Tenancy, config | `tenancy/`, `config/tenants/*.yaml` |
| Canonical model | `canonical/catalog.py` (see `MASTER_ENTERPRISE_DATA_MODEL.md`) |
| Data access | `connectors/`, `mapping/`, `query/` |
| Planning and decisions | `planning/` (see `UNIVERSAL_SCENARIO_ENGINE_ARCHITECTURE.md`) |
| AI | `agent/` (providers, tools, planning_tools, grounding, terminology, smalltalk) |
| Auth | `auth/` (dev, OIDC), `api/auth.py` (sections) |
| Audit and observability | `audit/`, `core/logging.py`, `/api/health` |
| Synthetic data | `synthetic/` (alpha, beta, gamma, delta) |
| Web | `apps/web/src/app/(app)/*`, `components/*`, `lib/hooks.ts` |

## Deployment shape

- **Today:** Docker images for API and web, plus a compose smoke test in CI. Proposed hosting is Vercel (web) and Render (API). Steps are in `FINAL_PRODUCT_AUDIT.md` §14; nothing is deployed.
- **Enterprise options:** customer-hosted (Docker or Kubernetes in-region) or private cloud in a Saudi region. External AI stays off unless the tenant approves it.
- **Heavy planning runs** execute synchronously within query timeouts. A background job queue is added only when measured data volumes require it (`PRODUCTION_READINESS_ASSESSMENT.md`).
