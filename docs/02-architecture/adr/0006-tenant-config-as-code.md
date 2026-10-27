# ADR-0006: Tenant configuration as validated YAML in the repository

- **Status:** Accepted
- **Date:** 2026-10-26
- **Session:** S01
- **Related:** brief §5.2, §15; REQ-003, REQ-053

## Context
Each customer differs in connection, schema mapping, roles, policies and coding rules. The brief requires configuration over customer-specific branching. No admin UI exists yet, and mapping changes must be reviewable and approvable.

## Decision
- One YAML file per tenant in `services/api/config/tenants/`, validated by Pydantic at startup (unknown keys rejected).
- Secrets never inline: `secret_ref: env:NAME` (later: vault references).
- Git history is the change/approval log for mappings until the mapping studio (M5) adds an approval workflow backed by the app DB.

## Consequences
- + Reviewable diffs; customer sign-off can reference a commit.
- + Zero code changes to onboard a schema.
- − Runtime edits need a redeploy/restart until M5.

## Alternatives considered
- DB-stored config from day one: needs admin UI + approval workflow first.
- Env vars only: unmanageable for mappings.

## Revisit when
M5 mapping studio.
