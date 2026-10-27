# Context Flow

Two flows matter: **(A)** how a user's request travels through the system, and **(B)** how anyone (human or LLM) works on this repository.

---

## A. Runtime flow — a request through the system

### A1. Dashboard widget / inventory page (Milestone 1, no AI)

```
Browser (Next.js page, React Query)
  │  GET /api/metrics/inventory_value_by_warehouse     (same-origin; cookie `lumiant_session`)
  ▼
Next.js rewrite  /api/*  ──►  FastAPI  (http://127.0.0.1:8000)
  ▼
1. Request context middleware   assigns request_id, starts timer, structured log line
2. Auth dependency              reads cookie → AuthProvider (dev: HS256 JWT) → Principal
                                Principal = {user_id, tenant_id, roles, permissions, warehouse_scope}
                                tenant comes ONLY from the token, never from the request
3. Permission check             route requires e.g. `dashboard:read`; metric requires `cost:read`
4. Metric catalog               metric id → versioned QueryPlan template + rule text
5. Validator                    dataset approved & mapped for tenant? fields exist? ops valid?
                                sensitive fields allowed? inject `warehouse_id IN (scope)`;
                                auto-group by currency / uom; cap limit
6. Compiler                     canonical plan + tenant mapping → SQLAlchemy Core SELECT
                                (physical table/column names, bound parameters, labels = canonical names)
7. SQL guard                    sqlglot parse: exactly one SELECT, only mapped tables, no system objects
8. Connector (per tenant)       read-only engine, timeout, fetch limit+1 → ResultSet (Decimal-safe)
9. Provenance                   source object + columns via mapping, user filters + injected filters,
                                data as-of, metric id/version, row count, truncated, synthetic flag
10. Audit                       append event (user, tenant, action, dataset, decision, rows, duration) — no values
11. Response                    {data, columns, provenance, warnings}; Decimals as strings
  ▼
Browser renders chart/table + provenance popover + SYNTHETIC badge + as-of
```

Failure paths: any step can stop the request with a **safe error** (`{error: {code, message, request_id}}`); the audit store records denials (`decision=deny`, reason code) as well as successes. No SQL, file paths, stack traces or credentials are ever returned.

### A2. Chat question (Milestone 3 — designed, not built)

```
question → auth → agent loop (LLM chooses tools, ≤4 calls)
        → each tool call goes through steps 4–10 above (same validator, same scope injection)
        → composer builds answer + chart spec → grounding guard (every number must come from results)
        → UI renders answer, table/chart, provenance, editable query chips, follow-ups
```
The LLM never sees credentials or physical SQL and cannot widen scope: scope is injected by code after the LLM has produced its plan. See `01-product/AGENT_DESIGN.md`.

### A3. Data onboarding flow (Milestone 5/7 — designed)

```
approved warehouse connection → schema discovery → profiling → mapping (human-approved)
  → validation run → reconciliation vs customer authoritative report → capability matrix → go-live
```

---

## B. Working flow — how every session works on this repo

```
1. ORIENT     read docs/00-context/CURRENT_STATE.md → latest logs/WORKLOG.md entries
              → 05-plan/IMPLEMENTATION_PLAN.md (next unchecked item)
2. CHECK      git status; confirm the code matches CURRENT_STATE (if not, log the drift first)
3. PLAN       state the step, the files it touches, and how it will be verified
4. IMPLEMENT  small increments; preserve working behaviour; tests written alongside
5. VERIFY     run the relevant checks (see 06-operations/TESTING.md) — never skip silently
6. LOG        after EVERY step:
                - logs/WORKLOG.md      append entry (template below)
                - logs/TEST_RUNS.md    append every check run with exact command + result
                - 05-plan/IMPLEMENTATION_PLAN.md   tick only verified items
                - new decision → 02-architecture/adr/NNNN-*.md + logs/DECISION_LOG.md line
                - new limitation/bug → logs/ISSUES.md
                - behaviour change → update the topic doc (API_CONTRACTS, DATA_MODEL, …)
7. CLOSE      end of session: rewrite 00-context/CURRENT_STATE.md, finalize
              logs/sessions/<date>-session-NN.md, update 01-product/ACCEPTANCE_CRITERIA.md,
              add logs/CHANGELOG.md entry for user-visible changes
```

### WORKLOG entry template

```markdown
## YYYY-MM-DD · S## · M#-step-# · <short title>
- **Goal:** …
- **Done:** …
- **Files changed:** …
- **Commands + results:** `…` → …
- **Decisions:** … (→ ADR-NNNN)
- **Issues / limitations:** … (→ ISSUES.md #)
- **Next:** …
```

### Hard rules for any contributor (human or LLM)

1. Never connect to a real customer system, use production credentials, or deploy without explicit written authorization from Lumiant (record it in the session log).
2. Never present synthetic data as customer data. The UI badge and the API `synthetic` flag must stay.
3. Never let the LLM produce executable SQL or authoritative numbers.
4. Never weaken or delete a test to make code pass. Fix the code or record the failure.
5. Never log or document secrets, tokens, connection strings or real customer values.
6. Commits only when the repo owner asks; follow the owner's git identity rules (see `CLAUDE.md`).
