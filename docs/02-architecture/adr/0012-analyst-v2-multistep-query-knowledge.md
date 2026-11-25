# ADR-0012: Analyst v2 — multi-step tool loop, `query_inventory`, knowledge retrieval

- **Status:** Accepted
- **Date:** 2026-11-25
- **Session:** S10
- **Related:** ADR-0002 (LLM never writes SQL), ADR-0009 (Gemini), ADR-0010 (context, streaming), `05-plan/PRODUCT_V2_PLAN.md` §6

## Context
The owner wants the assistant to answer "all sorts of" inventory questions with Gemini and "proper RAG". Before this change the model picked tools once (`decide → run → compose`), could only use the 21 named analyses, and had no way to look up definitions or methods.

## Decision
1. **Bounded multi-step loop.** After each round the service sends the results back (`GeminiProvider.advance`); the model either asks for more tools or writes the answer. Limits: 4 calls per round, 10 per question, 5 rounds; the last round is forced to text (`function_calling_config: NONE`). The rule-based provider still decides once; Anthropic keeps the single compose step.
2. **`query_inventory` tool.** The model fills a small typed shape (dataset, group_by, measures, filters, order, limit ≤ 100) that becomes a `QueryPlan` and runs through the same validator, scope injection, SQL guard, audit and provenance as the dashboard. This is the `query_inventory(QueryPlan)` tool ADR-0002 already allowed. The model sees the canonical catalog for its tenant and role (`catalog_note`): no physical names, no cost fields without `cost:read`. Rejections return to the model as failed results so it can correct the plan; floats become exact decimal strings.
3. **Knowledge retrieval (`lumiant.knowledge`).** Curated product text (metrics, costing methods, planning terms, trust and security, ERP terminology) plus the canonical catalog descriptions, chunked by section. BM25 keyword search always works offline; when an approved Gemini provider is active, `gemini-embedding-001` (768 dims) vectors are fused by reciprocal rank. Exposed as the `search_knowledge` tool, which returns a `sources` block that the UI shows as numbered citations. The offline matcher routes definition questions ("how is X calculated", "what does X mean") to it.
4. **Grounding unchanged in spirit.** Model wording is used only if the final round's tools all succeeded and every number in it is in the results (knowledge passages count as evidence, since they are product text). Otherwise the template answer is shown.

## Consequences
- + Questions outside the named analyses become answerable without the model ever writing SQL; security stays in application code.
- + Definitions are answered from reviewed text with citations, also without any external AI.
- − More model calls per question (latency, cost); bounded by the limits above. Not measured live yet (ISSUES #13).
- − Knowledge vectors are cached per process (recomputed after a restart); keyword search covers the gap.
- − `query_inventory` cannot bucket dates yet (no `date_trunc` in `QueryPlan`); trends need that op (plan P4).

## Alternatives considered
- Text-to-SQL with a validator: rejected by ADR-0002.
- A vector database service: unnecessary for a few hundred product chunks; revisit for tenant documents at scale.
