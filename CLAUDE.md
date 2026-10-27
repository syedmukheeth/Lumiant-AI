# Lumiant Inventory Intelligence Platform

AI-powered inventory intelligence for Lumiant Group's customers: read-only connection to a customer's data warehouse → canonical inventory model → secured deterministic query engine → dashboard, chat agent, reports. Multi-customer by configuration. **All data is synthetic** until a customer approves real data.

## Start every session here
1. `docs/00-context/CURRENT_STATE.md` (imported below)
2. latest entries of `docs/logs/WORKLOG.md`
3. `docs/05-plan/IMPLEMENTATION_PLAN.md` → next unchecked item
4. `docs/README.md` for the map of everything else

@docs/00-context/CURRENT_STATE.md

## Hard rules
- Never connect to a real customer system, use production credentials, or deploy without written authorization (record it in the session log).
- Never present synthetic data as customer data; keep the `synthetic` flag and UI badge.
- The LLM never writes SQL or produces authoritative numbers (ADR-0002). All data access goes through `services/api/src/lumiant/query/`.
- Authorization is server-side only; scope is injected by the validator.
- Money and quantities: `Decimal` in Python, strings in JSON, never float; never sum across currencies or units.
- Never weaken or delete a test to make code pass.
- No secrets, tokens, connection strings or real customer values in code, logs or docs.
- Commits only when the owner asks; follow the owner's global git rules (identity, no AI attribution lines).

## Logging protocol (after EVERY step)
Append `docs/logs/WORKLOG.md` · record every check in `docs/logs/TEST_RUNS.md` · tick `docs/05-plan/IMPLEMENTATION_PLAN.md` only when verified · new decision → ADR in `docs/02-architecture/adr/` + `docs/logs/DECISION_LOG.md` · new limitation → `docs/logs/ISSUES.md` · behaviour change → update the topic doc. End of session: rewrite `CURRENT_STATE.md`, finish `docs/logs/sessions/<date>-session-NN.md`, update `docs/01-product/ACCEPTANCE_CRITERIA.md`.

## Layout
- `services/api/` — FastAPI (Python 3.13 via uv). `src/lumiant/{core,tenancy,auth,canonical,mapping,connectors,query,analyses,metrics,audit,synthetic,api}`; tenant configs in `config/tenants/`.
- `apps/web/` — Next.js 16 (TypeScript 5.9, Tailwind 4, Recharts, React Query).
- `docs/` — knowledge base.

## Commands
See `docs/06-operations/DEV_SETUP.md` and `docs/06-operations/TESTING.md`. Always run Python via `uv run` (no system python). Paths contain a space — quote them.
