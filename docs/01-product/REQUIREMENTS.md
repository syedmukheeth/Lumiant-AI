# Requirements

Each requirement has an ID, the master-prompt section it comes from, its target milestone, and its status (vocabulary in `docs/README.md`).
Requirements are derived from the brief only — nothing customer-specific is invented (see `00-context/FACTS_ASSUMPTIONS.md`).

## Functional

### Data integration (brief §5, §6)
| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| REQ-001 | Connector interface: connect, inspect metadata, execute authorized read-only queries, normalized results, failure/health reporting, schema-change detection | §5.1 | M1 (core), M5 (discovery), M7 (real DB) | Designed |
| REQ-002 | Only claim support for connectors that are implemented **and tested** | §5.1 | all | Designed |
| REQ-003 | Per-tenant mapping from source tables/columns to the canonical model without changing core code | §5.2 | M1 | Designed |
| REQ-004 | Schema discovery (tables, columns, types, keys, dates, ids, quantities, costs, classifications, freshness) with human review for ambiguity | §5.3 | M5 | Not started |
| REQ-005 | Read-only access; no inserts/updates/deletes on source systems | §5.4 | M1 | Designed |
| REQ-006 | Canonical core model plus configurable extension attributes (≈100+ item fields) | §6 | M1 | Designed |
| REQ-007 | Configurable item-code parsing and validation rules per tenant | §6.2 | M2 | Not started |
| REQ-008 | Provenance for important answers: source system, dataset, fields, filters, timestamp, rule, mapping | §6.3 | M1 | Designed |

### Classification and levels (brief §7, §8)
| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| REQ-010 | Multiple independent classifications: stage, ABC, item group, storage requirements | §7 | M1 (as assigned), M2 (computed ABC) | Designed |
| REQ-011 | ABC thresholds/methods configurable; support customer-assigned ABC | §7.2 | M2 | Not started |
| REQ-012 | Storage-policy violations only when reliable data exists; never inferred from item names | §7.4 | M2 | Not started |
| REQ-013 | Low stock / reorder monitoring using customer-defined policies only | §8 | M1 (below-reorder) | Designed |
| REQ-014 | Excess, ageing, slow-moving, dormant, stockout indicators, warehouse comparison, imbalance, high-value monitoring | §8 | M2 | Not started |
| REQ-015 | Every alert explains why it was flagged and the underlying data | §8 | M1+ | Designed |

### Costing (brief §9)
| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| REQ-020 | Dedicated deterministic calculation layer; AI never invents financial numbers | §9 | M2 | Not started |
| REQ-021 | FIFO operational issue suggestion using authoritative receipt dates/lots | §9.1 | M2 | Not started |
| REQ-022 | LIFO only as configured operational rule; never auto-applied to valuation | §9.2 | M2 | Not started |
| REQ-023 | Average costing per approved method (moving WA, periodic WA, other) with txn types, currency, UoM, periods | §9.3 | M2 | Not started |
| REQ-024 | Lot costing where reliable lot data exists | §9.4 | M2 | Not started |
| REQ-025 | Explicit latest-price definition | §9.5 | M2 | Not started |
| REQ-026 | Cost comparisons (latest vs avg, lot vs avg, by item/warehouse/supplier/time/group) | §9.6 | M2 | Not started |
| REQ-027 | Decimal-safe arithmetic, documented rounding, explicit currency; unit tests with known results | §9.6 | M1 (Decimal + currency rails), M2 | Designed |

### AI agent and query engine (brief §10, §11)
| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| REQ-030 | Natural-language questions answered via structured plan → validation → read-only execution → evidence | §10 | M3 | Designed |
| REQ-031 | Structured plan contains intent, dataset, fields, filters, grouping, sort, aggregations, time range, limit, visualization, scope | §10.1 | M1 (plan core), M3 | Designed |
| REQ-032 | Honest handling: missing data, out-of-scope, ambiguity (clarify), stale data (disclose), safe errors; no fabrication | §10.2 | M1 (warnings), M3 | Designed |
| REQ-033 | Retrieved content treated as untrusted; security enforced in code | §10.3 | M1, M3 | Designed |
| REQ-034 | Query engine independently testable; approved objects only; parameterized; reject DML, unauthorized joins/columns; limits, timeouts; no system tables; tenant/department restrictions; audit; no secrets in errors | §11 | M1 | Designed |
| REQ-035 | Security tests for malicious prompts, unauthorized requests, malformed queries, restricted data | §11 | M1 (non-AI), M3 (AI) | Designed |

### UX (brief §12, §13)
| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| REQ-040 | Professional dashboard; only metrics whose data and definition exist | §12 | M1 | Designed |
| REQ-041 | Navigation adapted to permissions | §12 | M1 | Designed |
| REQ-042 | Chat interface with history, loading/error states, suggestions, tables, charts, freshness, calculation explanation, sources, feedback | §12 | M3 | Not started |
| REQ-043 | Graphical menu invoking the same secured services | §12 | M4 | Not started |
| REQ-044 | Tables, bar/line/donut charts, cards, comparisons, grouped/sorted/filtered reports | §13 | M1 (subset), M4 | Designed |
| REQ-045 | Visualization changes never alter filters/calculations; chart config validated | §13 | M3/M4 | Not started |
| REQ-046 | CSV/Excel export and printable reports, backend-enforced permissions, with timestamps/currency/filters/source | §13 | M4 | Not started |

### Access control and tenancy (brief §14, §15)
| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| REQ-050 | Server-enforced RBAC with configurable permission matrix | §14 | M1 | Designed |
| REQ-051 | Restrictions by tenant, department, warehouse, data domain, dataset, operation, sensitive field | §14 | M1 (tenant, dept, warehouse, dataset, op, sensitive field) | Designed |
| REQ-052 | Tests proving users cannot exceed permissions, including via the AI engine | §14 | M1, M3 | Designed |
| REQ-053 | Multi-customer via configuration; strict tenant isolation | §15 | M1 | Designed |

### Advanced intelligence (brief §17)
| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| REQ-060 | Each advanced feature documents inputs, rule, assumptions, missing data, confidence meaning, traceability, tests, recommendation≠action | §17 | M2+ | Not started |
| REQ-061 | No obsolescence prediction from stock quantity alone | §17 | M2+ | Designed (constraint) |

## Non-functional

| ID | Requirement | Src | M | Status |
|---|---|---|---|---|
| NFR-001 | Security controls listed in `03-security/SECURITY_PLAN.md` | §16 | M1–M6 | Designed |
| NFR-002 | Minimize data sent to AI provider; provider approval required | §16 | M3 | Designed |
| NFR-003 | Structured logging + audit metadata without sensitive values; configurable retention; audit access controlled | §19 | M1 (audit store), M5 (explorer) | Designed |
| NFR-004 | Server-side pagination, DB-side aggregation, row limits, timeouts, pooling, permission-aware caching | §22 | M1 (pagination, limits, timeouts), M6 (cache) | Designed |
| NFR-005 | Responsive, accessible, information-dense UI; demo data clearly labelled | §21 | M1 | Designed |
| NFR-006 | Configurable deployment; no assumption of public hosting | §4 | M6 | Designed |
| NFR-007 | Dev auth can never run in production | §20 Ph3 | M1 | Designed |
| NFR-008 | Documentation kept current; every step logged in Markdown | §3.3, owner instruction | all | In progress |
