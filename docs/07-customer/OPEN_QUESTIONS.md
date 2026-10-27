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
