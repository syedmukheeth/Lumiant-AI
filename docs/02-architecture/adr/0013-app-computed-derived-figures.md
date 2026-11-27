# ADR-0013: App-computed derived figures, inventory levers and a daily AI allowance

- **Status:** Accepted (owner, 2026-11-27)
- **Date:** 2026-11-27
- **Session:** S11
- **Related:** ADR-0002 (LLM never writes SQL), ADR-0009 (Gemini), ADR-0012 (multi-step loop), DEC-036, DEC-037

## Context
The owner wants the Analyst to answer real business questions ("what should I do to make 200000 profit next
month", "where is cash tied up", "how did value change"). ADR-0012's prompt forbade the model any arithmetic, so it
could not say how two figures compare. Open business questions fell through to "I can't answer that yet". External
AI was approved on no tenant, and the public demo had no cap on model spend.

## Decision
1. **App-computed figures (`calculate`).**
   - The model may ask the application for a sum, difference, ratio, percentage change or share of figures it
     already received in this question.
   - It cites each figure by reference to a result cell (`c<call>.r<row>.<field>`, shown on every row the model
     sees). It may also cite a number that already appears in the results or in the user's question.
   - The application looks the figures up and takes the unit from the row (currency, unit of measure, count,
     percent). It refuses to combine different currencies or units and computes in Decimal with half-up display
     rounding.
   - The result is a tool output, so the grounding check can trace it. ADR-0002's rule stands: **the model never
     writes SQL and never produces a number**. Only its wording changes: "no arithmetic of its own" replaces
     "no new figures".
2. **Inventory levers (`inventory_levers`).** A deterministic tool sizes what inventory data can see for a business
   goal:
   - stock above maximum
   - stock not issued in 270 days
   - expired lots, and lots expiring within 90 days
   - pairs below reorder level and pairs without a policy
   - stock lines without a valuation price

   Values come from one scoped `stock_balance` query (cost access only), attributed per pair in Decimal, per
   currency, never added across levers. The tool states what the data cannot show: no sales history, selling prices
   or margins, so no profit figure. The built-in matcher routes goal questions to it, so this works without any AI.
3. **Evidence without run metadata.** Timings, request ids and SQL no longer count as evidence (LA-10). Earlier
   answers passed back as history are context for the model, never evidence.
4. **Daily AI allowance (DEC-037).**
   - Every external model call spends one unit from a rolling 24-hour window per tenant: choosing tools, each review
     round, and each embedding. The default is 300.
   - When the allowance is spent, the Analyst answers with built-in matching and says so.
   - A 45-second deadline stops further model rounds for one question.
   - Gemini output is capped at 1024 tokens, temperature 0.2.
5. **Approval.** External AI is approved on the four synthetic demo tenants (owner). A `customer_extract` tenant can
   never be approved: the tenant model refuses it, and `sap_tenant_config` refuses approval for non-synthetic data.

## Consequences
- \+ Open business questions get a useful, honest answer from data, with recommended actions, even in rules mode.
- \+ Comparisons and percentages are possible without trusting model arithmetic.
- − The allowance is per instance unless the Redis store is configured (ISSUES #63).
- − Lever values are a floor when more than 200 rows are flagged, or when a pair holds several units or currencies;
  the answer says so.

## Alternatives considered
- Let the model compute and verify afterwards: rejected; a correct-looking number the check cannot trace would be
  withheld anyway, and a "close" one is worse.
- Sum the levers into one "cash to free" figure: rejected; they overlap (a dormant item can also be in excess).
