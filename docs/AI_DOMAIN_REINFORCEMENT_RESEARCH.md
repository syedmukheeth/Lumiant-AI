# Lumiant AI — Zero-Cost Domain Reinforcement and Open ERP Data Research

**Date:** 19 Nov 2026 · **Code inspected:** `work/resume-phase-b` @ `c1cc4e1` (PR #6) · **Cost incurred:** none. No paid API, dataset, GPU or training job was used.
**Verification labels:** **Verified** = read from the code or from the source page itself on 19 Nov · **Search only** = seen in a search result, not opened · **Inferred** = my reading, not stated by the source.

> **Not legal advice.** Licence conclusions below are an engineering screen. Lumiant sells commercially, so have counsel confirm before any external dataset is used in the product or in model training.

---

## Part 1 — Baseline: what the assistant does today

| Question | Answer (Verified in code) |
|---|---|
| 1. Which providers are implemented? | Three in `services/api/src/lumiant/agent/providers.py`: `RuleBasedProvider` (built-in matching), `AnthropicProvider`, `GeminiProvider`. `build_provider()` picks one |
| 2. Is an LLM actually invoked? | **No.** `agent_provider` defaults to `"rules"` (`core/config.py`); there is no `.env` and no API key; no tenant has `ai.external_provider_approved: true` (only demo-gamma declares it, as `false`). Every answer in the audits returned `mode: "rules"` |
| 3. Which model is configured? | Defaults `agent_model = "claude-opus-5-5"` (Anthropic) and `gemini_model = "gemini-flash-latest"`. Neither has ever been called live; tests use fake clients |
| 4. Can the model select structured tools? | Yes, by design. 13 typed tools in `agent/tools.py` (`TOOLS`, Pydantic args with `extra="forbid"`), filtered by role (`tools_for`). The LLM may only pick a tool and fill its arguments, never write SQL (ADR-0002). In rules mode, regular expressions pick the tool |
| 5. How is inventory terminology interpreted? | **By hand-written English regular expressions** in `RuleBasedProvider.decide()` and `_DIM_PATTERNS`, e.g. `reorder|low stock|running low`, `expir|shelf life`, `not moved|dormant|slow moving`. There is **no synonym dictionary, no ERP vocabulary and no Arabic** (0 Arabic characters in `providers.py`) |
| 6. How are ERP table and field names understood? | **The assistant never sees them.** Each tenant's YAML (`config/tenants/*.yaml`) maps physical tables and fields to the canonical model (`canonical/catalog.py`, `mapping/resolver.py`), e.g. `stock_value = ZV_STOCK.LABST * ZV_STOCK.VERPR`. The prototype `lumiant/nomap/packs.py` holds SAP field meanings and Odoo, Oracle EBS, Dynamics F&O and Business Central table knowledge, but it is **not wired into the product** |
| 7. Unfamiliar terminology? | Falls through to `"I can't answer that yet. Here are things I can do:"` plus five suggested questions. One special case declines "obsolescence" with an explanation |
| 8. Ambiguous questions? | Partly handled. An item name matching several items returns `kind: "clarify"` with choices; a cost question for an item held in several warehouses asks which one. Value-versus-quantity, currency and period ambiguities are resolved silently by defaults (e.g. value if the role may see costs) |
| 9. Unmapped field? | The analysis raises a capability error and the API returns **409** ("This analysis needs lot expiry dates, which are not mapped for this tenant"). The UI shows "Needs more data" (fixed in `c1cc4e1`) |
| 10. How are answers verified? | `agent/grounding.py`: every number in the answer must appear in the tool results (display rounding to 2–3 decimals of a real value is allowed). A failing built-in sentence is **withheld**; failing model prose is rejected and the template is used (`agent/service.py`). Query safety comes from the shared engine: validator, scope injection, sqlglot guard, read-only DuckDB |
| Conversation history | `agent/context.py` `HistoryTurn` keeps only the question, tool and arguments, never result data. Follow-ups ("what about quantity?") re-run tools |
| Evaluation sets | `services/api/evals/golden.yaml` (24 routing cases), `adversarial.yaml` (13 security cases), `services/api/eval/nomap/` (84-question prototype evaluation incl. a real Odoo 18 demo) |

**Shortcomings that matter for SAP, Odoo, Oracle Fusion and Saudi customers:**
1. **Brittle phrasing.** Common ERP wording fails or misroutes. "Unrestricted stock in plant 1100", "on-hand per subinventory", "quants in WH/Stock", "GRN", "goods issue", "SKU" and "bin" are not recognised. The 11 Nov audit found 9 everyday phrasings unsupported; 7 were fixed in `c1cc4e1`.
2. **No Arabic** questions, terms or answers.
3. **No explanation tool.** "What is ABC classification?" or "What does LABST mean?" cannot be answered.
4. **The ERP knowledge exists only in the unwired prototype.**
5. **The LLM path is untested live**, so its domain behaviour is unknown.

---

## Part 2 — Reinforcement techniques evaluated (no paid services)

**Principle kept throughout:** never teach any model stock levels, prices or values. Those are dynamic facts and always come from the customer's authorised data through the tools. What we teach is **meaning**: concepts, ERP representations, field-to-term mappings, which tool answers which question, and how to explain a verified result.

| # | Technique | Works today (rules)? | Helps an LLM later? | Cost | Value for Lumiant | Verdict |
|---|---|---|---|---|---|---|
| 1 | Domain system instructions | No | Yes | Free | Medium | Prepare now, activate with an LLM |
| 2 | **ERP terminology dictionary** (concept → synonyms in SAP/Odoo/Oracle/plain English) | **Yes**: normalise the question before matching | Yes: goes in prompt and tool descriptions | Free | **High** | **Do first** |
| 3 | RAG over a glossary and schema notes | Yes, with local keyword search (no embedding API) | Yes | Free | Medium: powers "explain" answers and LLM context | Do after #2 |
| 4 | **ERP schema knowledge packs** (SAP, Odoo, Oracle Fusion) | Indirectly: suggests mappings at onboarding | Yes | Free | **High** for onboarding speed | Promote from `nomap` into mapping *suggestions* (never bypassing the query engine) |
| 5 | Canonical model enrichment (stock-status categories, goods receipt and issue, consignment, unit conversion) | Yes | Yes | Free | Medium | Incremental, as customers need it |
| 6 | Structured tool descriptions (synonyms and examples per tool) | No | Yes | Free | Medium | Cheap; do with #1 |
| 7 | Few-shot examples | No | Yes | Free | Medium | Generate from the eval set |
| 8 | Synthetic instruction datasets | For evaluation, yes | Only via fine-tuning, which costs money or GPU time | Free to create from templates | Low now | Build for **evaluation**, not training |
| 9 | **Automated Q&A evaluation** (paraphrases EN/AR, ERP jargon, adversarial) | **Yes** | Yes | Free | **High**: measures every change | **Do first, alongside #2** |
| 10 | Ambiguity handling (ask value or quantity? which currency or warehouse? which period?) | Yes | Yes | Free | Medium–High | Do after #2 |
| 11 | **English–Arabic terminology mapping** | **Yes**: Arabic synonyms in #2 plus Arabic normalisation | Yes | Free | **High** for the Saudi market | Seed from Odoo's LGPL-3 Arabic translations (Part 3) and own curation |

### Recommended zero-cost combination

1. **Terminology layer** (`agent/terminology.py`). One curated table maps each canonical concept (on-hand, unrestricted, quality inspection, blocked, reorder point, safety stock, batch/lot, goods receipt, goods issue, transfer, warehouse/plant/inventory org, location/storage location/subinventory/bin, item/material/product/SKU, …) to its SAP, Odoo, Oracle Fusion and plain-English names **and Arabic terms**. It normalises questions before rule matching, and later feeds the LLM prompt and tool descriptions. It needs no model and works immediately.
2. **Arabic support for questions**: Unicode normalisation (alef forms, ta marbuta, diacritics, Arabic-Indic digits) plus Arabic entries in #1. Arabic *answers* (templates and right-to-left rendering) come as a second step.
3. **Evaluation first**: grow `golden.yaml` from 24 to about 150 cases. Add English paraphrases, SAP/Odoo/Oracle jargon and Arabic questions, each with the expected tool and arguments, and track pass rate per category so every change is measured.
4. **Ambiguity rules**: ask instead of guessing when value-versus-quantity, currency or warehouse is unclear and the difference changes the answer.
5. **Explain tool** backed by local keyword retrieval over the glossary ("What is ABC class?", "What is MARD?"), answering definitions only, never figures.
6. **Knowledge packs as onboarding suggestions**: SAP (have), Odoo (have, verified on Odoo 18), Oracle EBS and Dynamics (have, unconfirmed), plus a new **Oracle Fusion pack** from Oracle's public table reference (unconfirmed until a real export). Suggestions only; a human approves the mapping.
7. **LLM-ready assets kept free**: system prompt, enriched tool descriptions and few-shot examples drawn from the eval set, ready for when a provider is approved.

**Fine-tuning:** not recommended now. It needs paid training or GPUs, and the techniques above give most of the gain at no cost.

**Free LLM options, with caveats** (none set up):
- **Gemini free tier:** Google may use free-tier prompts to improve its products (noted in `services/api/.env.example`), so use it only with synthetic data, never customer data, and only after approval.
- **Local open-weight models:** this laptop has 7.7 GB RAM, which limits it to about 3–4B-parameter models with modest tool-use quality.

---

## Part 3 and Part 4 — Open ERP data: catalogue and licence audit

### A. SAP

| Resource | Owner | What it is | Format / size | Real or synthetic | Licence | Commercial use | Training / fine-tuning | Redistribution, attribution, share-alike | Gated | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| [SAP/SALT](https://huggingface.co/datasets/SAP/SALT) (**Verified**) | SAP SE | Sales documents, items, customers, addresses (`I_SalesDocument`, `I_SalesDocumentItem`, `I_Customer`, `I_AddrOrgNamePostalAddress`) + joined table | 120 MB, 10M–100M rows | **Real** ERP data | **CC BY-NC-SA 4.0** | **No** | Non-commercial only | NC + share-alike + attribution | Yes (agree to share contact info) | **Exclude.** Non-commercial, and sales, not inventory |
| [SAP/SALT-KG](https://huggingface.co/datasets/SAP/SALT-KG) (**Search only**) | SAP SE | Knowledge-graph benchmark companion to SALT | — | — | CC BY-NC-SA 4.0 (per search) | No | Non-commercial only | NC-SA | — | **Exclude** |
| [SAP-samples/datasphere-content](https://github.com/SAP-samples/datasphere-content) (**Verified**) | SAP SE | Sample CSVs + models for Bikes Sales, Retail POS Analytics, FI/HR/SD, openSAP course, Telecom CVM; a `SAP_Procurement_Finance_Spend` folder (contents not checked) | CSV, DDL | Synthetic sample | **Apache-2.0** "except as noted in the LICENSE file" (REUSE-compliant) | Yes, if no exception applies | Yes (Apache imposes no use restriction) | Keep licence/NOTICE; attribution | No | **Usable but low relevance.** No MM/inventory data confirmed; check LICENSE exceptions and the procurement folder before use |
| SAP-samples/analytics-cloud-datasphere-community-content (**Search only**) | SAP SE | Community analytics content | — | Sample | States it is "forbidden to sell these content samples or use them commercially" | **No** | — | — | — | **Exclude** |
| [SAP-samples/hana-shine](https://github.com/SAP-samples/hana-shine) (**Verified** licence; data **Inferred**) | SAP SE | SHINE demo on the EPM (Enterprise Procurement Model): procurement-style data model, tables, views | Delivery unit (.tgz) | Sample/demo | **Apache-2.0** "except as noted"; a third-party mirror says later SHINE-XSA versions moved to the **SAP Sample Code License** (**Search only**) | Depends on version | Depends on version | — | No | **Maybe**, for procurement concepts. Confirm the exact version's LICENSE first |
| [SAP-samples/hana-ml-samples](https://github.com/SAP-samples/hana-ml-samples) (**Verified**) | SAP SE | PAL/APL SQL and Python notebooks | Code | — | Apache-2.0 | Yes | — | Attribution | No | **Not a dataset** (code only) |
| [SAP-samples/hana-cloud-learning](https://github.com/SAP-samples/hana-cloud-learning) (**Verified**) | SAP SE | Learning content + some sample data (e.g. `travelroute.zip`) | Mixed | Sample | Apache-2.0 | Yes | Yes | Attribution | No | **Low relevance.** No inventory data confirmed |
| [lucesgabriel/sap_mm_dataset](https://huggingface.co/datasets/lucesgabriel/sap_mm_dataset) (**Verified**) | Individual | 10,777 SAP MM question/answer pairs (`input`, `output`, `instruction`) | JSON, 4.6 MB | Likely LLM-generated (**Inferred**) | **None declared**, so all rights reserved | **No** | **No** | — | No | **Exclude.** No licence, unknown quality |
| SAP data dictionary facts (MARA, MARD, MCHB, MSEG/MATDOC, MBEW, EKKO/EKPO …) | SAP SE (docs) | Table and field meanings | — | — | SAP documentation copyright | Facts only | Facts only, in our own words | Don't copy text | — | **Use as knowledge.** Already captured in `nomap/packs.py` ("unconfirmed on a real SAP system") |
| SAP ABAP Platform Trial (from 5 Nov research) | SAP SE | Developer trial system | Docker image (~170 GB disk, 16–32 GB RAM) | Demo | SAP developer licence, non-production (**Search only**) | No production use | Not for training data export (**Inferred**) | No | Docker Hub login | **Internal testing only**, if hardware allows |

**SAP conclusion:** no openly licensed **inventory/MM** dataset was found. The one real SAP dataset (SALT) is non-commercial and sales-only. Lumiant's own synthetic SAP-style tenants plus documented field semantics remain the right path.

### B. Odoo

| Resource | Owner | What it is | Version | Licence | Commercial | Training | Redistribution | Verdict |
|---|---|---|---|---|---|---|---|---|
| [odoo/odoo `addons/stock`](https://github.com/odoo/odoo/blob/18.0/addons/stock/__manifest__.py) (**Verified**) | Odoo S.A. + contributors | Stock models (`stock.quant`, `stock.move`, `stock.location`, `stock.lot`, `stock.warehouse.orderpoint`, …), 5 demo-data files (`stock_demo_pre.xml`, `stock_demo.xml`, `stock_demo2.xml`, `stock_orderpoint_demo.xml`, `stock_storage_category_demo.xml`) | **18.0** branch | **LGPL-3** | Yes | Yes (LGPL restricts distribution of modified code, not use) | Under LGPL-3 with notices | **Best source.** Schema and demo data verified live on a real Odoo 18 database (`eval/nomap/odoo/`) |
| [odoo/odoo `addons/stock/i18n/ar.po`](https://github.com/odoo/odoo/tree/18.0/addons/stock/i18n) (**Verified**) | Odoo translators | **Arabic** translations of every stock-module UI term (56 languages available) | 18.0 | LGPL-3 | Yes | Yes | Keep attribution/licence for any copied strings | **Use** to seed the Arabic terminology layer (curate; record source and licence) |
| [pantalytics/odoo-demo-data](https://github.com/pantalytics/odoo-demo-data) (**Verified**) | Pantalytics | Fictional company "universes" (e.g. coffee roaster) with cast, product catalogue, customers, CRM, BOMs, projects | Not stated | **MIT** | Yes | Yes | Keep MIT notice | **Usable** for demo storylines; inventory/stock not confirmed. Its loader uses Claude Code + an Odoo MCP server, and its image step needs a paid FLUX key, so skip that part |
| Odoo version differences (**Verified** fact) | — | Field names change across versions (e.g. `stock.production.lot` → `stock.lot` in newer releases; product names and costs are JSON per language/company in v17+) | — | — | — | — | — | Packs must be **version-keyed**. Do not assume v18 fields on v14–16 customers |

### C. Oracle Fusion Cloud SCM

| Resource | Owner | What it is | Licence | Verdict |
|---|---|---|---|---|
| [REST API: inventoryTransactions POST](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/op-inventorytransactions-post.html) (**Verified**) | Oracle | Schema for `/fscmRestApi/resources/11.13.18.05/inventoryTransactions` (marked **deprecated**): `OrganizationName`, `Subinventory`, `Locator`, `Item`, `Revision`, `TransactionQuantity`, `TransactionUOM`, `TransactionType`, lot (`LotNumber`, `LotExpirationDate`) and serial arrays, flexfields. Two example payloads (miscellaneous receipts) | No open licence shown; Oracle documentation copyright applies (**Inferred**) | **Knowledge only.** Use field semantics in our own words; don't copy or redistribute examples. Two payloads are not a dataset |
| [Fusion SCM Tables and Views](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/oedsc/overview.html) (**Search only**) | Oracle | `INV_ONHAND_QUANTITIES_DETAIL` (on-hand as a FIFO stack of receipt records), `INV_ONHAND_QUANTITIES_SUMMARY`, `INV_MATERIAL_TXNS` (every material transaction), `INV_MATERIAL_TXNS_TEMP` (staging), `EGP_SYSTEM_ITEMS_B` (item master); release-specific pages 24A–26B | Oracle documentation | **Use for an Oracle Fusion knowledge pack**, labelled unconfirmed until a real BICC/BI Publisher export is tested |
| [oracle-samples](https://github.com/oracle-samples) (**Verified**) | Oracle | Only `fdi-custom-extractors` (UPL-1.0) relates to Fusion Data Intelligence. It's an SDK, not data | UPL-1.0 | **No inventory dataset** |
| FDI Content Library workbooks (**Search only**) | Oracle | Analytics workbooks with example business questions; need an FDI subscription | Not verified | **Not usable** without a subscription |

**Oracle Fusion conclusion:** **no downloadable, openly licensed Oracle Fusion inventory dataset could be verified.** Oracle Database sample schemas are a different system and are not Fusion data. The realistic routes are:
- a **customer or partner test-pod export**, under contract;
- a **synthetic Fusion-shaped tenant** built from the documented table and field semantics.

### D. Generic supply chain (not ERP-specific)

| Resource | Licence | Verdict |
|---|---|---|
| [DataCo Smart Supply Chain](https://data.mendeley.com/datasets/8gx2fvg2k6/5) (**Search only**; licence per Mendeley comparison page for versions 4–5) | **CC BY 4.0** | **Usable** with attribution for generic orders, shipping and product vocabulary and for demo questions. Not inventory-ledger data. Confirm the version's licence on the page |

---

## Recommendation and next steps (all zero-cost)

1. **Build the terminology layer and expanded evaluation set first** (Part 2, items 1 and 3), seeding Arabic terms from Odoo's LGPL-3 `ar.po` with attribution. This is measurable within days and needs no AI provider.
2. **Add Arabic question normalisation and ambiguity prompts.**
3. **Add an Oracle Fusion knowledge pack** from Oracle's public table reference, and make all packs version-keyed onboarding *suggestions*.
4. **Keep LLM assets ready** (prompt, tool descriptions, few-shot), and activate only with a key plus tenant approval. Never send customer data to a free tier.
5. **Exclude** SALT, SALT-KG, the community-content repo and the unlicensed HF SAP MM set from product and training use.

### Implementation status (19 Nov 2026, uncommitted)

Steps 1 and 2 (normalisation) and the glossary half of step 4 are built. Cost: zero. Nothing was trained, and no paid or external call was made.

| Piece | Where | What it does |
|---|---|---|
| Terminology layer | `services/api/src/lumiant/agent/terminology.py` | About 30 concepts (warehouse, location, item group, stage, stock status, on-hand, value, reorder, excess, dormant, expiry, lot, data quality, special storage, cost, ABC, …). Each one carries its SAP, Odoo and Oracle Fusion names and Arabic terms, and maps them to Lumiant's canonical wording. It holds meanings only, never quantities, prices or values. |
| Arabic normalisation | same module | Unifies alef forms, ى/ي, ة/ه, ؤ and ئ, and strips diacritics and tatweel. Converts Arabic-Indic and Persian digits to ASCII, so item and warehouse codes typed in Arabic still resolve. Turns Arabic durations ("ستة أشهر", "شهرين", "٣٠ يوما") into days. |
| Built-in matcher | `agent/providers.py` `RuleBasedProvider.decide` | Matches against the question plus canonical hints. The original words come first, so existing phrasings behave as before. Word-count rules (follow-ups, vague questions) still count only the user's words. Two incidental fixes: "above the reordering rule maximum" now routes to excess, and SAP "unrestricted" stock is no longer read as a restricted-status breakdown. |
| LLM prompts | `AnthropicProvider` / `GeminiProvider` | A short glossary of the terms found in the question is appended to the system prompt. It is used only when a key and tenant approval exist. |
| Evaluation set | `services/api/evals/terminology.yaml` | 79 cases: SAP (20), Odoo (8), Oracle Fusion (7), plain English (8), Arabic (30) and permissions (6). The permission cases check that a role without cost access never sees a currency in any vocabulary. Run with `pytest tests/integration/test_agent.py -k terminology`. |
| Unit tests | `tests/unit/test_terminology.py` | 23 tests covering normalisation, hints, Arabic durations, item-code hints, and a guard that no concept carries figures or currency. |

Result: the full API suite has 583 passed and 6 skipped (Redis and Postgres tests that need external services). Before this change it had 480. Ruff, ruff format and mypy are clean. Arabic coverage is Modern Standard business Arabic. Gulf dialect phrasing and transliterated Arabic ("kam qeemat al makhzoon") are not covered yet.

### Reinforcement with the client's own SAP exports (20 Nov 2026)

The client's two exports, "Warehouse Stocks of Material" (MB52 layout) and "Material Master", were used to check the assistant. They were not used as training data.

- **How:** they were loaded with the documented local intake (`lumiant-ingest sap`, see `docs/07-customer/CLIENT_DATA_INTAKE.md`) into `services/api/var/private/`. That folder is git-ignored and the tenant is `customer_extract`, which never uses external AI. The control totals matched exactly and every compared line reconciled.
- **Check:** 129 questions were run against the real data. The run printed only routing results (expected tool versus chosen tool), never answers or figures.
- **Found and fixed:**
  - Every warehouse question failed with HTTP 400. The tools assumed plant names exist, but an SAP extract without T001W has plant ids only. They now group by plant id. The synthetic twin `demo-gamma` had the same gap, so `test_warehouse_questions_work_without_warehouse_names` covers it without real data.
  - "transit and transfer", "restricted-use", "value in quality inspection" and "value unrestricted" are now understood as SAP stock-status and value terms.
  - "no price", "zero price", "no ABC indicator" and "no material master" now reach the data-quality check.
  - "valuation class" is no longer read as "valuation".
  - "materials worth the most" now reaches the value ranking.
  - Grouping by a field no tool supports yet (unit of measure, valuation class, MRP type, purchasing group) now gets a clear answer instead of an item search.
- **Result:** 122 of 129 questions routed correctly before the fixes, and 129 of 129 after. The phrasing, but none of the data, was added to `evals/terminology.yaml` as 25 cases on `demo-gamma`, so CI keeps it covered.
- **Not used:** quantities, values, prices, descriptions and user ids. Nothing from the files is committed or stored outside `var/private/`. The client's own Z material types still read as unmapped until the client explains them (Q-019).

Still open: step 3 (an Oracle Fusion knowledge pack as onboarding suggestions), ambiguity prompts, and Arabic answers in the built-in templates. Today the built-in assistant answers Arabic questions in English, while an approved LLM is asked to reply in the user's language.

Sources:
- [SAP/SALT](https://huggingface.co/datasets/SAP/SALT), [SAP SALT announcement](https://news.sap.com/2025/04/sap-salt-real-erp-dataset-enterprise-ai-research), [SALT-KG](https://huggingface.co/datasets/SAP/SALT-KG)
- [datasphere-content](https://github.com/SAP-samples/datasphere-content), [REUSE status](https://api.reuse.software/info/github.com/SAP-samples/datasphere-content), [community content](https://github.com/SAP-samples/analytics-cloud-datasphere-community-content)
- [hana-shine](https://github.com/SAP-samples/hana-shine), [hana-shine-xsa](https://github.com/SAP/hana-shine-xsa), [hana-ml-samples](https://github.com/SAP-samples/hana-ml-samples), [hana-cloud-learning](https://github.com/SAP-samples/hana-cloud-learning)
- [lucesgabriel/sap_mm_dataset](https://huggingface.co/datasets/lucesgabriel/sap_mm_dataset)
- [Odoo stock manifest (18.0)](https://github.com/odoo/odoo/blob/18.0/addons/stock/__manifest__.py), [Odoo stock i18n](https://github.com/odoo/odoo/tree/18.0/addons/stock/i18n), [pantalytics/odoo-demo-data](https://github.com/pantalytics/odoo-demo-data)
- [Oracle inventoryTransactions REST](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/fasrp/op-inventorytransactions-post.html), [Fusion SCM tables overview](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/oedsc/overview.html), [INV_ONHAND_QUANTITIES_DETAIL](https://docs.oracle.com/en/cloud/saas/supply-chain-and-manufacturing/26a/oedsc/invonhandquantitiesdetail-6068.html), [oracle-samples](https://github.com/oracle-samples)
- [DataCo (Mendeley)](https://data.mendeley.com/datasets/8gx2fvg2k6/5), [version comparison](https://data.mendeley.com/datasets/compare/8gx2fvg2k6)
