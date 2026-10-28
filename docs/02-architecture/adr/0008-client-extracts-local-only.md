# ADR-0008: Client extracts are local-only, classified `customer_extract`

- **Status:** Accepted
- **Date:** 2026-10-27
- **Session:** S03
- **Related:** `../../07-customer/CLIENT_DATA_INTAKE.md`, Q-013, Q-019…Q-026, ADR-0004, ADR-0006

## Context
The client sent two real SAP exports. The owner wants to analyse them now, before any production setup exists, and
decided: real files only on the owner's machine, never committed, no real values in code/logs/docs, and a synthetic
twin with the same layout for CI and demos. The platform so far knew two classifications: `synthetic` (demo data,
dev sign-in) and `customer` (production, IdP only, no dev users). Neither fits a confidential snapshot that a
developer opens locally.

## Decision
1. New `data_classification: customer_extract`.
2. **Where it may live:** its tenant YAML is accepted only from `LUMIANT_PRIVATE_TENANTS_DIR` (and that directory
   accepts nothing else); its DuckDB path must be under `var/private/` (git-ignored, plus explicit `.gitignore`
   lines and a test running `git check-ignore`). The repository's `config/tenants/` refuses it.
3. **Where it may run:** `LUMIANT_PRIVATE_TENANTS_DIR` is refused unless `LUMIANT_APP_ENV=development`;
   `LUMIANT_ALLOW_CUSTOMER_EXTRACTS` is refused in production; the app factory refuses to start in production if any
   extract tenant is loaded (defence in depth).
4. **Who may sign in:** dev users of an extract tenant are listed and accepted only when the environment is
   development **and** `LUMIANT_ALLOW_CUSTOMER_EXTRACTS=true`; otherwise they do not exist for the dev provider.
5. **How it is labelled:** `/api/meta/tenant` and every provenance carry `data_classification`; the shell shows
   "CLIENT EXTRACT · CONFIDENTIAL · LOCAL" instead of the synthetic tape; exports carry a CONFIDENTIAL notice and a
   `CONFIDENTIAL-` file-name prefix.
6. **AI:** the existing tenant flag `ai.external_provider_approved` stays `false` in generated configs; external AI is
   therefore off for extracts until the client approves it (Q-013). No new flag was added: the existing one already
   gates every external call.

## Consequences
- Real data can be analysed with the same secured engine (scope, cost permission, audit, guard) without weakening
  the synthetic/customer separation.
- A developer must opt in twice (private directory + flag), which is deliberate friction.
- The repository never contains the client tenant, so CI cannot exercise it; the `demo-gamma` twin (same importer,
  same mapping generator) covers the pipeline instead.
- The extract is a snapshot: "data as of" is the extract date and the UI will show it as stale after 36 hours.

## Alternatives considered
- Treat the extract as `customer`: would forbid dev sign-in, so it could not be opened locally without an IdP.
- Treat it as `synthetic`: would mislabel real data as generated — violates the hard rule.
- Keep the files outside the platform and analyse in a notebook: loses the guard, scope, audit and provenance.

## Revisit when
The client approves a real connection (M7), an IdP is available (Q-010) or external AI is approved (Q-013).
