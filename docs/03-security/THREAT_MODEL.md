# Threat Model

Method: assets → actors → threats → mitigations → residual risk. Revisit every milestone.

## Assets
Customer inventory and cost data · warehouse credentials · session tokens · tenant configuration (mappings, roles) · audit trail · AI prompts and results.

## Actors
A legitimate user going beyond their scope · a user of another tenant · an attacker with no session · malicious text inside source data · an AI provider · an insider with repo access · operator misconfiguration.

## Threats

| ID | Threat | Mitigation | Residual |
|---|---|---|---|
| T-01 | Reading warehouses outside scope (filters, plan, AI) | Validator injects scope; explicit out-of-scope filter → 403; per-role tests | Scope-derivation bugs → covered by tests |
| T-02 | Reading cost fields without permission | Sensitivity tags; validator checks select/filter/sort/aggregate; cost columns stripped from rows | Every new field must be tagged (catalog review) |
| T-03 | Cross-tenant access | Tenant only from token; one engine per tenant; no tenant parameter; tests | Shared hosting widens the blast radius → infra review (A-007) |
| T-04 | SQL injection | No string SQL; bound params; escaped LIKE; sqlglot guard; read-only DB | — |
| T-05 | Data modification | No write paths; guard rejects non-SELECT; DB opened read-only | — |
| T-06 | Expensive queries / DoS | Row caps, timeouts, `in`-list limit, pagination; rate limiting in M6 | No rate limiting until M6 |
| T-07 | Session theft or forgery | httpOnly/SameSite cookie; signature and expiry checked; HTTPS in prod | Dev secret resets with each process |
| T-08 | Dev auth running in production | Startup guard; dev endpoints return 404 outside dev; tests | — |
| T-09 | Internals leaked in errors | Global handler maps exceptions to safe codes; tests | — |
| T-10 | Secrets committed or logged | `.gitignore`, `secret_ref`, redaction rules | Human error → CI secret scanning (M6) |
| T-11 | Prompt injection through data (M3) | Data passed as quoted results; no privilege-changing tools; grounding guard; planted test rows | Misleading prose → grounding + provenance |
| T-12 | Over-sharing with the AI provider (M3) | Data boundary, caps, sensitive fields stripped, disclosure log, approval, AI-off mode | Provider retention → handled by contract (Q-013) |
| T-13 | XSS through data values | React escaping, CSP, no raw HTML | — |
| T-14 | CSRF | SameSite=Lax + custom header; same-origin | — |
| T-15 | Wrong numbers shown as fact | Currency/UoM rails, provenance, as-of, synthetic flag, independent-SQL tests, reconciliation (M5) | Real mapping errors → reconcile before go-live |
| T-16 | Audit tampering or exposure | Append-only; `audit:read`; tenant-scoped reads | DB admins → platform controls |
| T-17 | Supply chain | Lockfiles, pinned versions, audits | CI scanning in M6 |
