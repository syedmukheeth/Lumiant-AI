# ADR-0009: Gemini as an optional external AI provider

- **Status:** Accepted
- **Date:** 2026-10-28
- **Session:** S04 (plan Part C)
- **Related:** ADR-0002, Q-013, ISSUES #13; `../../01-product/AGENT_DESIGN.md`

## Context
The owner wants the assistant to understand free-form questions better than the built-in matcher, and chose the Gemini API. The Anthropic adapter already exists but has no approved key. ADR-0002 still applies: a model may only choose typed tools and word the answer.

## Decision
1. `GeminiProvider` (`agent/providers.py`) implements the same `decide` / `compose` contract as `AnthropicProvider`, through the official `google-genai` SDK (pinned `>=2.27,<2.28`). Automatic function calling is disabled; the model returns function calls, the application validates the arguments and runs the tool. Tool declarations are generated from the tool argument models (titles and `additionalProperties` removed; no-argument tools declare no parameters).
2. Configuration: `LUMIANT_AGENT_PROVIDER=gemini`, `LUMIANT_GEMINI_API_KEY` (secret, `.env` only), `LUMIANT_GEMINI_MODEL` (default `gemini-flash-latest`, the alias Google keeps on the current Flash model; pin an exact id for reproducibility). Timeout 30 s; any failure falls back to the built-in matcher with a notice.
3. Same gates as Anthropic: the tenant must set `ai.external_provider_approved: true`, a key must exist, the model sees at most 20 rows per result with fields cut to 120 characters, prose is checked by the grounding guard, every call is audited (`agent:disclosure`).
4. The model receives the screen context as validated ids only (ADR-0010) and earlier turns as "question → tool + arguments", never earlier results.

## Consequences
Free-form questions can be answered on approved tenants; numbers stay deterministic. The client extract (`customer_extract`) keeps external AI off until the client approves a provider. **The Gemini API free tier may use prompts to improve Google's products: use a paid key before any client data can reach it.** Verified only with a fake client here (ISSUES #13 now covers both providers).

## Alternatives considered
Gemini's automatic function calling (would execute Python callables chosen by the model — conflicts with ADR-0002's validation step). Vertex AI / enterprise endpoint (needs a Google Cloud project; can be added via `genai.Client(enterprise=True, …)` when hosting is decided, Q-012).

## Revisit when
The client approves a provider (Q-013); a live-API check is possible; the SDK's major version changes.
