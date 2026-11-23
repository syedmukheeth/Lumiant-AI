# Implementation Roadmap — Universal Planning

_22 Nov 2026. Status labels: Implemented and tested · Implemented but not fully verified · Partially implemented · Planned · Blocked._

| Phase | Scope | Status | Evidence / what remains |
|---|---|---|---|
| 0 Discovery and architecture | inspection, licence audit, data model, scenario catalogue, architecture | Implemented and tested | `UNIVERSAL_SCENARIO_ENGINE_ARCHITECTURE.md`, `SCENARIO_CATALOGUE.md`, `SCENARIO_DATASET_AND_LICENSE_AUDIT.md`, `MASTER_DATA_MODEL.md` |
| 1 Master data foundation | supplier master, supplier–item, BOM header/revision/lines, alternates, lead times, synthetic data | Implemented and tested | catalog datasets; `demo-delta`; loader. **Remaining:** FX rates dataset, transfer lanes dataset, per-field provenance. |
| 2 Customer demand and MRP | orders, availability, aggregation, BOM explosion, gross/net, shortages, open supply, safety stock, time-phasing, fulfilment | Implemented and tested | `planning/mrp.py`, S01–S16, C-A/B/I/M/N. **Remaining:** forecast demand, statistical safety stock, FEFO lot selection, large-volume read path. |
| 3 Supplier and procurement intelligence | prices, history, MOQ, delivery and quality metrics, comparison, landed cost, pre-PO recommendation | Implemented and tested | `planning/suppliers.py`, C-C/G/H/L, S48–S63. **Remaining:** supplier risk scoring, price breaks and charges from canonical data, FX source. |
| 4 Production and alternatives | multi-level BOM, substitution, lead times, calendars, make-or-buy, capacity, multi-plant | Partially implemented | Done: multi-level, phantoms, revisions, substitution, calendars, per-plant make/buy, transfers. **Blocked/planned:** routings, work centres, capacity, downtime, co-/by-products, rework, subcontracting, make-or-buy costing. |
| 5 Master data quality and obsolescence | duplicates, attributes, lifecycle, criticality, supersession | Implemented and tested | `duplicates.py`, `obsolescence.py`, S69, S74, C-E/F/K. **Remaining:** supplier code matching (71), attribute completeness rules per item group (72), expiry action test (79). |
| 6 Scenario engine and AI orchestration | capability registry, combined scenarios, clarification, comparison, explainability | Implemented and tested (built-in matcher) | `scenario.py`, `planning_tools.py`, 8 routing tests. **Remaining:** live LLM verification (no key; external AI not approved), a planning workspace page. |
| 7 Testing and hardening | scenario suite, security, regression, builds | Partially implemented | API 753 passed; lint and types clean. **Not run this session:** web e2e (a new tenant now appears on the dev sign-in page), CI on GitHub. |

## Enterprise transformation phases (23 Nov 2026 brief)

| Phase | Status | Evidence / remaining |
|---|---|---|
| 0 Discovery | Done | `ENTERPRISE_PRODUCT_AUDIT.md`, `MASTER_ENTERPRISE_ARCHITECTURE.md`, `ENTERPRISE_SECURITY_REVIEW.md`, `PRODUCTION_READINESS_ASSESSMENT.md` |
| 1 Brand and UI foundation | **Done (23 Nov)** | Official logos (theme-aware, sidebar logo 160 px, teal line removed) and brand palette from the artwork; Plan/Procure/Govern navigation. Remaining: executive dashboard planning tiles, supplier directory |
| 2–5 Master data, MRP, procurement, master-data quality | Engine, API, assistant **and web workspaces** done | `/planning`, `/suppliers`, `/master-data`. Remaining: supplier directory page, FX and lanes datasets, capacity (blocked), forecasting |
| 5b Customer commitment protection | **Done (23 Nov)** | Delivery-first sourcing, revenue/margin/penalty exposure, premium analysis, split sourcing, what-if table, `/commitments` dashboard, assistant tool; scenarios P, Q, R. Remaining: production capacity in completion dates (blocked on routings), per-tenant thresholds |
| 6 Scenario engine | Done for the built-in matcher | live LLM blocked (no key or approval) |
| 7 Hardening | Open | LA-01, LA-06, LA-11 (incl. planning routes), LA-13, observability, load test, backups |
| 8 Final validation | Partial | API 754, web unit 78, e2e 29 (with production build), lint and typecheck green; no deployment |

## Next priorities

1. ~~Planning workspace in the web app~~ — **done 23 Nov** (`/planning`, `/suppliers`, `/master-data`). Next: e2e tests for these pages, column selection and export, and a supplier directory page.
2. ~~Official logos and brand tokens~~ — **done 23 Nov**. Next: verify OIDC with a Keycloak container in CI; rate limits on the remaining routes; SQL-aggregated planning loader.
2. **Exchange-rate and transfer-lane datasets** in the canonical model, so multi-currency comparison and balancing work on tenant data, not only in fixtures.
3. **Client data requests** for real planning: SAP MARC (lead times, lot sizes, BESKZ), STKO/STPO (BOMs), EINA/EINE + EORD (info records, source list), VBAP/VBEP (open orders), EKPO/EKET (open POs with dates); Odoo `mrp.bom`, `product.supplierinfo`, `sale.order.line`.
4. **Capacity** once work centres and routings are available (scenarios 35–37), then make-or-buy costing.
5. **Large-volume loading:** aggregate stock and supply in the query engine instead of paging raw rows.
