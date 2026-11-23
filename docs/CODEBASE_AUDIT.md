# Lumiant AI: Codebase Audit and Final Report

**Audited:** `syedmukheeth/Lumiant-AI`, branch `main`, commit `647ef7b`, on 2026-10-31. Investigation only: no application code was changed, nothing was committed or pushed, and no customer system or real credential was touched.

**Labels:** **[V]** verified in code or by running it · **[R]** recommendation · **[A]** assumption · **[U]** unverified.

> **Update 2026-10-31, after the audit:** LA-02, LA-03 and LA-04 are **fixed** in the working tree (uncommitted; ISSUES #40–#42). The rest of this report records the audited state of `647ef7b` and is kept as written, so read references to those three findings as history. All other findings remain open, including LA-10 (limits of the grounding check itself). A second round of testing found LA-39 to LA-50, including a P0 browser leak across users: see [QUESTIONS_AND_LIMITATIONS.md](QUESTIONS_AND_LIMITATIONS.md), which also answers the audit's questions.

| Document | Covers |
|---|---|
| [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) | How it works today |
| [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md) | Weaknesses and target architecture |
| [ERP_INTEGRATION_ANALYSIS.md](ERP_INTEGRATION_ANALYSIS.md) | Each enterprise system |
| [AI_SCHEMA_DISCOVERY.md](AI_SCHEMA_DISCOVERY.md) | Schema discovery and mapping |
| [ENTERPRISE_DATA_ACCESS_AND_TRUST.md](ENTERPRISE_DATA_ACCESS_AND_TRUST.md) | Deployment models and customer trust |
| [SECURITY_AUDIT.md](SECURITY_AUDIT.md) | Threat model and vulnerabilities |
| [INVENTORY_DOMAIN_REVIEW.md](INVENTORY_DOMAIN_REVIEW.md) | Business logic and costing |
| [AI_QUERY_ENGINE_REVIEW.md](AI_QUERY_ENGINE_REVIEW.md) | Query engine and agent |
| [UI_UX_AUDIT.md](UI_UX_AUDIT.md) | Interface review |
| [TECHNICAL_BOTTLENECKS.md](TECHNICAL_BOTTLENECKS.md) | Performance |
| [PRODUCT_DIFFERENTIATION.md](PRODUCT_DIFFERENTIATION.md) | Where to compete |
| [OPEN_CUSTOMER_QUESTIONS.md](OPEN_CUSTOMER_QUESTIONS.md) | Customer questionnaire |
| [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md) | Prioritized plan |

---

## 1. Executive summary

**Lumiant is a well-engineered synthetic-data prototype with an excellent governed query core. It is not yet a product a customer could connect to.**

Its authorization design resisted every bypass attempted. All project tests pass. Its documentation is unusually honest. But:

- **It cannot connect to any customer system.** DuckDB is the only source type the configuration accepts.
- **It cannot be signed into in production mode.** The browser path is broken for OIDC.
- **Its "AI" is regex matching by default.** No external model has ever been called.
- **It can show wrong or invented figures**, in three reproduced defects that **all automated tests miss**.

Passing tests are real evidence, but of less than they appear. **375 API tests and 23 end-to-end tests pass while the main dashboard says 1 lot has expired when 29 have.**

The commercial problem you raised has a practical answer. Because the product is a compact monolith, it can run **inside the customer's own environment**, reading approved views through a read-only account, with AI off or restricted so the model never sees results. That avoids asking customers to hand over data, and it needs less engineering than a hosted agent architecture.

**Readiness:** demo-ready on synthetic data **after three small fixes**. Pilot-ready after a connector and customer-environment packaging. Enterprise-ready is a substantial programme.

## 2. What has actually been implemented

| Capability | Status | Evidence |
|---|---|---|
| Canonical inventory model (11 datasets) | Verified | `canonical/catalog.py` |
| Per-tenant YAML mapping, value maps | Verified | `mapping/resolver.py`, `test_mapping.py` |
| Query plan → validate → compile → guard → read-only execution | Verified | `query/`, probes |
| Warehouse scope, cost permission | Verified | probe 4 |
| Currency and unit rails | Verified | `validator.py:152-179` |
| Provenance on results | Verified | `query/service.py:245-300`, UI |
| Fail-closed audit log | Verified, one gap | `audit/store.py` |
| Moving average, FIFO, latest price | Verified on hand-computed cases | `test_costing.py` |
| Below-reorder, excess, dormant, data-quality | Verified | `test_m2_analyses.py` |
| Reports, CSV/XLSX, formula-injection protection | Verified | `reports/service.py` |
| Mapping drift check, capability matrix, reconciliation tool | Verified | `admin/service.py` |
| SAP export import with control-total gate | Verified on synthetic twin | `ingest/sap_exports.py` |
| Rate limiting (chat, query, export, login) | Verified, partial coverage | probe 14 |
| Nonce CSP, security headers | Verified | e2e, `proxy.ts` |
| CI on GitHub | Verified green on `647ef7b` | GitHub API |

## 3. What is simulated or incomplete

| Status | Item |
|---|---|
| **Simulated** | All demo data; "SAP" naming in demo-alpha is illustrative; demo-gamma is a generated twin |
| **Simulated** | External AI providers tested with fake clients only |
| **Simulated** | OIDC tested with local keys only |
| **Partial** | OIDC: API works, browser cannot (LA-01) |
| **Partial** | Grounding guard (LA-04, LA-10) |
| **Partial** | Computed ABC: on-hand basis, 1,000 item cap |
| **Partial** | RBAC: warehouse and cost only |
| **Partial** | Assistant: 5 of your 10 questions answered, 1 partial |
| **Partial** | SAP-layout tenant: assistant and some tiles fail |
| **Planned, not built** | Mapping approval, Material 360, saved views, drill-through, ageing, price alerts, OpenTelemetry, LIFO |
| **Code present, no caller** | `periodic_weighted_average`, `fifo_pick`, `list_objects`, `secret_ref` |
| **Missing** | Every real connector, schema discovery, background jobs, secrets vault, retention, deletion, backups, Helm/Terraform, pen test, certifications, FX, UoM conversion, history |

The real client SAP import was done on one machine and is not in the repository. It is a snapshot, not an integration.

## 4. Current architecture

A modular monolith: Next.js proxying to one FastAPI process, with per-tenant DuckDB files, tenant YAML, and an audit database. All data access flows through `QueryService`. See [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) for all ten walkthroughs and diagrams.

## 5. Architecture weaknesses

SQL-only connector contract; configuration as state; asserted join cardinality; a second, hand-built query path; analytics in Python; no background jobs; per-process state; build-time binding of web to API. **Keep the monolith.** See [ARCHITECTURE_REVIEW.md](ARCHITECTURE_REVIEW.md).

## 6. Integration readiness

**Zero of eight target systems are supported.** PostgreSQL is closest. SAP needs care: third-party ODP-RFC is not permitted and reportedly now blocked by patches, so a customer warehouse or published API is the route. Hyperion and Cognos are not stock sources. See [ERP_INTEGRATION_ANALYSIS.md](ERP_INTEGRATION_ANALYSIS.md).

## 7. Schema discovery readiness

**Not ready.** Mapped schemas work well; unknown ones cannot be discovered. Drift checking exists, but no discovery, relationships, profiling, scoring or approval. Build the validation harness first. See [AI_SCHEMA_DISCOVERY.md](AI_SCHEMA_DISCOVERY.md).

## 8. Enterprise data access recommendation

| Need | Recommendation |
|---|---|
| Default | **Model B**: whole stack in the customer's environment, read-only on approved views |
| Highly regulated | Model B, isolated, signed offline updates, AI off or local |
| Limited data sharing | Model A + C, aggregates only |
| External AI prohibited | Built-in matching or Model E |
| Launch | Metadata assessment → export pilot → Model B → agent later |

## 9. Privacy and trust strategy

Lead with: *your data stays in your systems, you control the read-only account, and AI is optional and can be limited to understanding the question.*

Introduce **intent-only AI** as the default: the model gets the question and permitted tool schemas, and never the results. Today, if enabled, up to 20 rows per tool including descriptions and values are sent, and the log records only a count. Three documented promises exceed the code (LA-07) and must be corrected before a customer reads them. See [ENTERPRISE_DATA_ACCESS_AND_TRUST.md](ENTERPRISE_DATA_ACCESS_AND_TRUST.md) for what may be claimed today.

## 10. Security gaps

Strong core; the gaps are edges and maturity: LA-01 browser OIDC, LA-04 unverified text, LA-06 passwordless-by-default, LA-07 AI boundary, LA-11 rate limits, LA-13 coarse permissions, LA-20 audit integrity. No pen test exists. See [SECURITY_AUDIT.md](SECURITY_AUDIT.md).

## 11. Inventory business logic gaps

Good discipline on money, currency and units. Key gaps: expiry counts, lot join, movement identity, ABC basis and cap, reversals, standard price, no slow-moving, ageing, stockout, FX, UoM conversion or history. Issuing policy and valuation need separate settings. See [INVENTORY_DOMAIN_REVIEW.md](INVENTORY_DOMAIN_REVIEW.md).

## 12. AI agent readiness

**Safe architecture, immature capability.** The model cannot write SQL, which is the right foundation. But it has never run live, and the default is regex. Grounding proves a number exists in tool output, not that it is right. See [AI_QUERY_ENGINE_REVIEW.md](AI_QUERY_ENGINE_REVIEW.md).

## 13. UI/UX assessment

Professional and credible; provenance is its best feature. The SAP-layout tenant shows rough edges, the data grid lacks detail views, and number formatting varies. Do not redesign. See [UI_UX_AUDIT.md](UI_UX_AUDIT.md).

## 14. Performance bottlenecks

Unknown at scale: **no load test exists.** Known: 52 warehouse queries per Overview load, hard 1,000-row analytic limits, and in-Python analytics. See [TECHNICAL_BOTTLENECKS.md](TECHNICAL_BOTTLENECKS.md).

## 15. Differentiation

Compete on **provable answers** rather than chat: reconciliation, data quality, cross-warehouse rebalancing, duplicate item detection, and later cross-system intelligence. See [PRODUCT_DIFFERENTIATION.md](PRODUCT_DIFFERENTIATION.md).

## 16. Questions requiring customer clarification

Nine must be answered first: source of truth, deployment location, connector permission, read-only views, AI policy, approvers, authoritative report, valuation method, and handling of files already supplied. See [OPEN_CUSTOMER_QUESTIONS.md](OPEN_CUSTOMER_QUESTIONS.md).

## 17. Roadmap

Trust fixes → foundation gaps → first real integration and customer-environment packaging (parallel) → AI intelligence → scale-out. See [PRODUCT_ROADMAP.md](PRODUCT_ROADMAP.md).

## 18. Top 10 next actions

| # | Action | Why now | Findings |
|---|---|---|---|
| 1 | Fix expiry counts, failure masking and ungrounded text, with regression tests | Wrong numbers end trust instantly | LA-02, 03, 04 |
| 2 | Make the repository private; settle ownership and licence | Public now, no licence | LA-21 |
| 3 | Get written handling terms for the client files, and confirm secure storage and deletion date | Open compliance exposure | LA-28 |
| 4 | Enforce join cardinality and correct lot and movement keys | Silent double-counting | LA-05, 17 |
| 5 | Send the nine must-answer questions; decide the first deployment model with the customer | Blocks everything customer-specific | Q-001, 012, 013 |
| 6 | Make development auth opt-in, and rate-limit all data routes | Unsafe defaults | LA-06, 11 |
| 7 | Build the source abstraction, PostgreSQL reference connector and conformance tests | Unlocks every SQL source | LA-08, 09 |
| 8 | Implement the browser OIDC flow and test with a real IdP | Production cannot sign in | LA-01 |
| 9 | Add intent-only AI and a real disclosure log; correct the AI docs; run one live test on synthetic data | Makes the trust story true | LA-07, ISSUES #13 |
| 10 | Build the mapping validation harness, then registry and approval | Proves mappings are right | LA-05, 19 |

---

# Appendix A: test evidence

Run on Windows 11, Python 3.13, Node 24, from a clean clone. Repo documents Node 22 in CI.

| Check | Result | Note |
|---|---|---|
| `uv sync --frozen` | Pass | uv installed in a scratch venv, outside the repo |
| `lumiant-synthetic generate --all` | Pass | ~68 s |
| `ruff check` / `ruff format --check` | Pass | 109 files |
| `mypy` strict | Pass | 79 source files |
| `pytest` | **375 passed, 6 skipped** in 193 s | Skips need live PostgreSQL/Redis |
| Coverage | **93%** (5,315 statements) | `ingest/cli.py` 0%, `synthetic/cli.py` 56% |
| `eslint`, `tsc` | Pass | |
| `vitest` | **50 passed** | |
| Playwright e2e | **23 passed** in 3.5 min | Production build; Chromium build 1248 installed for this |
| `pip-audit` with extras | **No known vulnerabilities** | |
| `pnpm audit` | **1 moderate**: `minimatch` <11.0.1, GHSA-g3hv-75wg-m249 | Dev-only via eslint. Repo log says 0; CI will likely fail on next run |
| Git history sweep | No data files or secret patterns | Pattern-based, not a guarantee |
| GitHub CI on `647ef7b` | Success | Read from public API |

**Not run:** Docker images (daemon not running), PostgreSQL/Redis suites locally (CI covers them), load tests, a real IdP, any live LLM, any real database connector, axe or screen-reader tests. **Light theme not assessed.**

**Probes:** 17 read-only scripts in the session scratchpad exercised behaviour against synthetic data. Fan-out and failure probes ran on temporary copies. A SQL Server result was re-tested with a modern dialect setting, and one apparent finding (`ROW_NUMBER` rejection) was dropped as an artefact.

**Why tests missed the defects.** Coverage measures execution, not correctness. `tests/integration/test_m2_analyses.py:102` asserts `expired + expiring == len(body["data"])`, so it **encodes the expiry defect as expected behaviour**; that assertion must change with the fix, and this is a correction, not a weakened test. No test injects a dead source into the insight feed, and I found none covering a model reply with no tool call. Add fault injection, low-limit cases compared with independent SQL, and a no-tool model reply.

# Appendix B: finding register

P0 blocks customer use · P1 before production · P2 hardening · P3 housekeeping. All findings [V] unless marked.

| ID | P | Finding | Location | Current behaviour | Recommended fix |
|---|---|---|---|---|---|
| LA-01 | P0 | OIDC unusable in browser | `apps/web/src/proxy.ts:19` | No cookie → `/login` | BFF with OIDC code flow |
| LA-02 | ~~P0~~ **Fixed** | Expiry counts wrong | `analyses/risks.py:261`, `insights/engine.py:271`, `agent/tools.py:380` | Shows 1 or 15; truth 29 | Separate count query (done, ISSUES #40) |
| LA-03 | ~~P0~~ **Fixed** | Failure shown as all-clear | `insights/engine.py:355-366`, `agent/tools.py:570` | Dead source: "Nothing stands out", cached | Per-rule status; do not cache failure (done, ISSUES #41) |
| LA-04 | ~~P0~~ **Fixed** | Invented numbers shown | `agent/service.py:222,243-246`, `answer-view.tsx:158` | USD 48,250,000 displayed | Block and show failure (done, ISSUES #42) |
| LA-05 | P0 | Silent double count | `canonical/catalog.py:212`, `query/compiler.py:87` | +USD 63,990.61 (2.31%), no warning | Composite key; activation tests |
| LA-08 | P0 | No customer connector | `tenancy/models.py:30`, `connectors/registry.py:30-32` | DuckDB only | Source abstraction |
| LA-06 | P1 | Unsafe defaults | `core/config.py:31-35`, `api/auth.py:61` | Passwordless dev login by default | Explicit dev opt-in |
| LA-07 | P1 | AI docs exceed code | `agent/providers.py:405-411`, `agent/service.py:262-272` | Values sent; count logged | Intent-only; content log; fix docs |
| LA-09 | P1 | Non-portable SQL | `query/sql_guard.py:16`, `query/compiler.py:140` | `LOWER` rejected; `NULLS LAST` on T-SQL | Dialect-aware; test matrix |
| LA-10 | P1 | Weak grounding | `agent/grounding.py`, `agent/service.py:217-221` | Words, ids, question pass | Typed evidence; placeholders |
| LA-11 | P1 | Partial rate limits | `api/inventory.py`, `api/insights.py`, `api/reports.py`, `api/metrics.py` | Unlimited | Global per-user budget |
| LA-13 | P1 | Coarse authorization | `query/validator.py:284`, `tenancy/models.py:78-81` | Items, suppliers unscoped; attributes uncosted | Policy classes |
| LA-16 | P1 | Row caps break features | `analyses/risks.py:586,671`, `api/inventory.py:63` | Errors or silent limits | SQL aggregation; warnings |
| LA-17 | P1 | Movement id too narrow | `config/tenants/demo-alpha.yaml:113`, `costing/engine.py:55-61` | Real lines would be dropped | Composite id |
| LA-18 | P1 | Query volume | Overview | 52 queries | Batch, cache |
| LA-19 | P1 | No schema discovery | `admin/service.py:46`, `connectors/base.py:51` | `list_objects` unused | Registry |
| LA-21 | P1 | Public, unlicensed repo | GitHub | `private=false`, no licence | Private; settle IP |
| LA-25 | P1 | Assistant coverage | `agent/providers.py:250` | 5 of 10 | Semantic metrics, model |
| LA-28 | P1 | Consent open for real data | `07-customer/OPEN_QUESTIONS.md` Q-023 | Imported; terms Open | Written terms |
| LA-32 | P1 | ABC on-hand basis only | `costing/abc.py` | No consumption basis | Configurable |
| LA-33 | P1 | ABC thresholds per request | `api/analyses.py:60` | Not stored | Tenant config |
| LA-34 | P1 | Reversals ignored | `analyses/risks.py:122` | Cancelled issue counts as movement [A: on real SAP data] | Net reversals |
| LA-12 | P2 | Sessions not revocable | `api/auth.py:78-81` | Replay accepted | Server sessions |
| LA-14 | P2 | AVG float | `query/compiler.py:31-32` | `887.2957746478874` | Cast |
| LA-15 | P2 | Pool timeout unhandled | `connectors/duckdb_connector.py:38-45` | 500 | 503 |
| LA-20 | P2 | Audit integrity | `audit/store.py` | No tamper evidence or retention | Hash chain, export |
| LA-22 | P2 | Supply chain | `.github/workflows/ci.yml` | No scanners; moderate advisory | Add; pin |
| LA-23 | P2 | Container concerns [U] | `apps/web/Dockerfile`, `next.config.ts:5` | Origin baked; possible runtime download | Standalone output |
| LA-26 | P2 | SAP tenant assistant | `agent/tools.py:186` | `warehouse.name` failure | Use `has_ref` |
| LA-30 | P2 | OIDC unknowns | `auth/oidc.py` | Real-IdP behaviour unknown | Test |
| LA-35 | P2 | Negative stock | `costing/engine.py:100` | Error | Configurable |
| LA-36 | P2 | Split valuation refused | ISSUES #23 | Import stops | Design later |
| LA-37 | P2 | No history | Model | Snapshot only | Snapshots |
| LA-24 | P3 | Stale docs | `README.md:5`, `ci.yml:2`, `DEPLOYMENT.md:3`, `SECURITY_PLAN.md` | Says Milestone 1, "never run" | Refresh |
| LA-31 | P3 | Report access nuances | `api/reports.py:33-40` | Preview without export right | Accept or tighten |
| LA-38 | P3 | Fixed reconcile tolerance | `analyses/risks.py:55` | Constant | Per tenant |

# Appendix C: credit where due

Things worth preserving and copying:

- `ADR-0002`: the model never writes SQL.
- The refusal to answer obsolescence without evidence.
- Control-total gating on import, and rounding-aware reconciliation.
- Gaps that name the missing SAP file.
- Client extract isolation (ADR-0008): layered, tested guards.
- `FACTS_ASSUMPTIONS.md`: a ledger separating known from assumed.
- Recording failures in `TEST_RUNS.md`, not just successes.

# Appendix D: audit side effects

- Clone at `C:\Users\SaadAdeeb\Lumiant-AI`, outside OneDrive to avoid syncing `node_modules`.
- `next dev` auto-generated untracked `apps/web/AGENTS.md`. Left in place, not deleted; delete or commit it.
- Ignored local artefacts: `node_modules`, `.next`, `services/api/data`, `services/api/var`.
- Playwright's Chromium added to the user's browser cache.
- `docs/logs/WORKLOG.md` and `TEST_RUNS.md` were **not** updated, although `CLAUDE.md` asks for it, because this audit was restricted to the 14 named documents. Record this audit there if you adopt it.
