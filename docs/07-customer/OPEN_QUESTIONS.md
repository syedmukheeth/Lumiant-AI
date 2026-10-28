# Open Questions for Lumiant / the customer

Answers unblock milestones. Record each answer with date, who answered, and source, then update `00-context/FACTS_ASSUMPTIONS.md`.
Priority: **H** blocks a milestone · **M** needed before production · **L** nice to know.

| ID | Question | Why we need it | Blocks | P | Status |
|---|---|---|---|---|---|
| Q-001 | Which data warehouse product and version holds the inventory data (SQL Server, Oracle, PostgreSQL, SAP HANA/BW, Snowflake, other)? How is it reached (network path, VPN, private link)? | Choose and test a connector | M7 | H | Open |
| Q-002 | Which tables/views are approved for the platform? Can the customer create dedicated read-only views? | Approved dataset list; least privilege | M7 | H | Open |
| Q-003 | Schema docs or sample DDL for item master, stock balances, lots/batches, transactions/movements, purchasing, costing/valuation, reorder policies, warehouses/locations | Mapping | M7 | H | Open |
| Q-004 | Item-coding rules (what positions/segments mean, validation rules) | Item-code parser | M2 (real) | M | Open |
| Q-005 | ABC: does the customer maintain assigned ABC classes? If we compute: value definition, period, thresholds? | ABC feature | M2 (real) | M | Open |
| Q-006 | Valuation method: moving weighted average, periodic weighted average, standard cost, FIFO? Treatment of returns, transfers, negative stock? | Costing engine | M2 (real) | H | Open |
| Q-007 | Accounting period calendar and closing rules | Periodic average, period comparisons | M2 (real) | M | Open |
| Q-008 | Definition of "latest price": latest valid purchase price or latest receipt cost? Which statuses count? | Latest-price metric | M2 (real) | M | Open |
| Q-009 | FX: which currencies, which rate source and rate-date rule, if any conversion is wanted | Multi-currency totals | M2 | M | Open |
| Q-010 | Identity provider (Microsoft Entra ID, Okta, ADFS, other), protocol (OIDC/SAML), group → role mapping | Production auth | M6 | H | Open |
| Q-011 | Department and warehouse hierarchy; who may see which warehouses and cost data | Permission matrix | M6 | H | Open |
| Q-012 | Hosting: customer cloud tenant, Lumiant-managed private cloud, on-prem? Region/data residency? Container platform? | Deployment design | M6 | H | Open |
| Q-013 | Is an external AI provider approved for confidential aggregates? Which (Anthropic API, AWS Bedrock, Google Vertex, Azure OpenAI, self-hosted)? Data-handling terms? | AI agent with real data | M3 (real) | H | Open |
| Q-014 | Retention periods for audit logs, chat history, AI disclosure logs | Retention controls | M6 | M | Open |
| Q-015 | Authoritative reports to reconcile against (stock valuation report, stock list) and acceptable variance | Go-live gate | M7 | H | Open |
| Q-016 | Data volumes (items, lines, transactions/yr), refresh frequency of the warehouse, freshness SLA, timezone | Performance, staleness warnings | M6/M7 | M | Open |
| Q-017 | Unit-of-measure conversions available? Where are they maintained? | Cross-UoM totals | M2 | L | Open |
| Q-018 | Lumiant branding/design guidelines for the UI, if any | UI polish | M4 | L | Open |
| Q-019 | SAP export intake (M8): what do the client's own **material types** mean (especially customer-specific Z-types)? Which count as raw, semi-finished, finished, spare, consumable? | Value map `item.inventory_stage`; today only SAP standard types are mapped, others read "unmapped" (`CLIENT_DATA_INTAKE.md` §3) | M8 | H | Open |
| Q-020 | Which **stock statuses** count as "available" inventory (unrestricted only, or also quality inspection, in transit, restricted, blocked, returns)? Should blocked/returns be valued in the headline figure? | Headline value and availability definitions | M8 | H | Open |
| Q-021 | **Valuation policy:** confirm moving average (V) vs standard price (S) per material/plant is authoritative, and how SAP value differences to quantity × price (moving-average drift) should be treated | Reconciliation tolerance, costing (Q-006) | M8 | H | Open |
| Q-022 | What do the client's **MRP types** mean (is `ND` really "no planning"; any custom types)? Which plants/locations should have planning? | Value map `item_warehouse.planning_type`, planning-gap insight | M8 | M | Open |
| Q-023 | **Consent and handling wording** for analysing the exports: may Lumiant keep the files locally for analysis, for how long, who may see results, how they are deleted? | Data handling (ADR-0008) | M8 | H | Open |
| Q-024 | Is an external AI (owner proposes **Google Gemini**, paid tier) approved for aggregates of these extracts? Data-processing terms? (Extends Q-013) | AI agent on client data; off until approved | M9 | H | Open |
| Q-025 | **Next files to request**: MB51/MSEG material movements for 24 months; MARC (reorder point, safety stock, max stock, MRP); MCHB/MCH1 (batch stock + shelf life / expiry); T001W/T001L (plant and storage-location names); EKKO/EKPO (purchase order lines); LFA1 (vendors). Same export format (XLSX with header row, codes as text, totals allowed) | Dormant, consumption, FIFO, below-reorder, excess, expiry, names, latest price (`CLIENT_DATA_INTAKE.md` §8) | M8 | H | Open |
| Q-026 | Some stocked lines have no master record for their plant, and some master records have zero price while stock exists: expected (e.g. not-yet-valuated materials) or extract gaps? Should a re-extract include them? | Completeness of value; data-quality findings | M8 | M | Open |
