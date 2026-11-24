# Universal Scenario Engine — Architecture

_Status: Phase 0 and the first slices of Phases 1–6 were implemented on 22 Nov 2026 (branch `work/resume-phase-b`, uncommitted). The status labels in this document match `SCENARIO_COVERAGE_MATRIX.md`._

## 1. What it is

Lumiant answers planning questions that combine several things at once: demand, stock, BOMs, alternates, suppliers, lead times and policies. It does this with **reusable deterministic capabilities**, not one hard-coded answer per example. A combined scenario is several capabilities run over the same planning data. Situations the engine does not support are reported as such, never answered as if they were solved.

```
question / event
  → context and scenario classification      planning/scenario.py  classify()
  → required data discovery and validation   planning/scenario.py  assess(); planning/loader.py
  → canonical data retrieval (secured)       planning/loader.py → query engine (scope, cost, audit)
  → business rules and planning calculation  planning/{bom,mrp,suppliers,transfers,duplicates,obsolescence}.py
  → what-if and alternatives                 same functions, different inputs or policies (e.g. C-A vs C-A2)
  → recommendation, explanation, provenance  planning/service.py (JSON-safe), agent/planning_tools.py
  → human review                             every result is labelled recommendation_only; nothing is executed
```

The LLM (when a tenant approves one) only interprets the question and picks tools. All quantities, dates, prices and scores come from the backend (ADR-0002). The built-in matcher routes the same questions without any external AI.

## 2. Components (code references)

| Layer | File | Responsibility |
|---|---|---|
| Domain model | `services/api/src/lumiant/planning/model.py` | Items, BOMs, alternates, stock lines with status and owner, reservations, scheduled supply, demand, planning policies, calendar, allocation policy, suppliers, offers, delivery and price history, FX, supplier policy. `Decimal` only; unknown lead time is `None`, never 0. |
| Calendar | `planning/calendar.py` | Working-day arithmetic. The default weekend is Friday + Saturday (Saudi Arabia); holidays are configurable. |
| Units | `planning/uom.py` | Item-specific or general conversions. With no conversion, the quantity is left out and reported. |
| BOM | `planning/bom.py` | Revision chosen by date, multi-level explosion, scrap and yield, phantoms, cycle and missing-component detection, low-level codes, where-used. |
| MRP | `planning/mrp.py` | Time-phased gross-to-net per item and warehouse, allocation policy, safety-stock protection, approved substitution (two-pass so alternates keep their own stock), lot sizing, merged planned orders, release dates, pegging, honest ready dates, fulfilment per order line with reasons, excess supply. |
| Suppliers | `planning/suppliers.py` | Eligibility (approval, status, mandatory certificates, validity, need date, quality and on-time gates), FX, price breaks, MOQ and multiples, landed cost with unknown charges disclosed, evidence-based quality, price vs history, configurable ranking, split sourcing. |
| Transfers | `planning/transfers.py` | Surplus after a warehouse's own demand → transfer options over allowed lanes, with arrival date and cost (unknown cost disclosed). |
| Item master | `planning/duplicates.py` | Probable duplicates, conflicts and different specifications, each with reasons; nothing is merged. |
| Lifecycle | `planning/obsolescence.py` | Obsolete candidate only when the item has no movement, no demand, no BOM use and is not critical; critical spares kept; superseded run-down. |
| Scenario layer | `planning/scenario.py` | Capability registry (status, required and optional data, triggers, scenario ids) and `assess()` → full / preliminary / clarify / unsupported, plus missing data, questions and capability gaps. |
| Data access | `planning/loader.py` | Canonical datasets → model, only through `QueryService.run_plan` (tenant isolation, warehouse scope, cost permission, row limits, audit). Truncation and missing dates become issues. |
| Service | `planning/service.py` | One entry point for API and assistant; staleness warning; audit record per run; capability gaps recorded as `planning:capability_gap`. |
| API | `api/planning.py` | `GET /api/planning/{fulfilment, material-plan, bom, suppliers, duplicates, lifecycle}`, `POST /api/planning/assess` (CSRF). |
| Assistant | `agent/planning_tools.py`, `agent/providers.py` `_planning` | 7 typed tools; the built-in matcher routes only when the tenant maps the needed datasets; answers pass the grounding check. |
| Test harness | `services/api/evals/scenarios/*.yaml`, `tests/unit/test_planning_scenarios.py` | Each scenario lists its inputs, rules and expected results; 85 checks. |
| Synthetic data | `synthetic/manufacturing.py`, `config/tenants/demo-delta.yaml` | Fictional manufacturer with planted situations and known outcomes. |

## 3. Configurability instead of hard-coding

- **Allocation of scarce stock:** `AllocationPolicy.keys`, e.g. `[due, priority, order_date]` or `[priority, due]` (S03 / S03b).
- **Supplier ranking:** `SupplierPolicy` with mode weighted / cheapest / fastest / quality, weights, a rejection limit, a minimum on-time %, minimum evidence, a certificate exception and the base currency. Built-in presets are `balanced`, `urgent`, `lowest_cost` and `quality_critical` (combined C shows the winner changing with the policy).
- **Lot sizing:** per item and plant (lot-for-lot, fixed, minimum, multiple).
- **Make or buy:** per plant (`item_warehouse.procurement_type`), because the same item can be made in one plant and bought in by a DC.
- **Substitution rules:** approval, ratio, priority, validity, maximum share, customer restriction.
- **Calendars:** weekend days and holidays.

Customer-specific rules that are not yet expressible are reported by `assess()` and recorded as capability gaps.

## 4. Unknown or unsupported scenarios

`assess(question, available)`:
1. classifies the question into capabilities (regex triggers, Arabic normalised);
2. lists the known facts (record counts in the user's scope);
3. lists the missing required data per capability and turns it into targeted questions;
4. lists the capabilities that are requested but only planned (capacity, forecasting …) as `capability_gaps`;
5. returns a mode: `full`, `preliminary` (some parts calculable and labelled so), `clarify` or `unsupported`.

The assistant's `planning_scope` tool and `POST /api/planning/assess` expose this. Gaps are written to the audit log as candidate new capabilities.

## 5. Security and governance (unchanged principles, now applied to planning)

- Reads go only through the query engine: tenant isolation and warehouse scope on orders, stock, purchase lines and plant data; `cost:read` is required for supplier prices (API, tool and matcher all refuse without it; tested).
- Read-only: there are no ERP writes, no purchase orders are created or approved, no records are merged, nothing is disposed of, no unapproved substitution is made.
- One supplier's quotation is never shown to another supplier. Lumiant has no supplier-facing access at all.
- Customer data never goes to an external model without tenant approval (existing ADR-0009 path).
- Every planning run is audited (`planning:*` actions), on top of the per-query audit.

## 6. Known limitations (honest)

- No exchange-rate dataset in the canonical model yet: offers in another currency are marked not comparable (tested on demo-delta).
- No work centres, routings or shift calendars, so capacity feasibility is reported as unsupported (scenarios 35–37).
- Forecasting and seasonality are not built (scenarios 17–18 partial or planned).
- Supplier evaluation uses per-item delivery history; supplier-level risk scores, landed-cost components beyond freight and duty, and price breaks from canonical data are not loaded yet.
- The loader reads up to 20 pages of the tenant's `max_rows`; larger datasets raise a `data_truncated` warning. A streaming or aggregated read path is needed for production volumes.
- The web UI has no dedicated planning pages yet. Planning is reachable through the assistant (all pages) and the API.
