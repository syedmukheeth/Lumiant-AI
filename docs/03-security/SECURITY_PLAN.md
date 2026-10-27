# Security Plan

The platform handles confidential business and financial data. Security is a design constraint, not a phase.
Each control has a status (vocabulary in `docs/README.md`) and a target milestone. Threat analysis: `THREAT_MODEL.md`.

## Principles

1. **Server-side enforcement only.** Never trust the frontend or the LLM for authorization.
2. **Defense in depth.** App validator → SQL guard → read-only DB account. Where possible each layer stops an attack on its own.
3. **Tenant isolation by construction.** Tenant comes from the token, and each tenant gets its own connector.
4. **Minimize data movement.** Aggregate in the DB, cap rows, and send the AI only what the answer needs.
5. **No secrets in code, logs, docs or errors.**

## Controls

| # | Control | Brief §16 item | M | Status |
|---|---|---|---|---|
| C-01 | Dev-only auth with production guard; OIDC with customer IdP later | Secure authentication | M1 / M6 | Verified (dev mode + guards); OIDC not started |
| C-02 | Authorization on every endpoint (route permission + metric permission + validator) | Server-side authorization | M1 | Verified |
| C-03 | Warehouse/department scope injected into every query | Least privilege, tenant isolation | M1 | Verified |
| C-04 | Sensitive-field control (`cost:read`) | Least privilege | M1 | Verified |
| C-05 | Read-only DB connectivity (DuckDB `read_only=True`; customer read-only accounts) | Read-only connectivity | M1 / M7 | Verified (DuckDB); customer DBs blocked |
| C-06 | Secrets via env / secret-manager refs; `.env` gitignored; `.env.example` holds no real values | Secret management | M1 | Verified (no secrets in repo; `.env` ignored) |
| C-07 | TLS at customer proxy/ingress; `Secure` cookies under HTTPS; HSTS at proxy | TLS | M6 | Designed |
| C-08 | Encryption at rest via deployment platform | Encryption at rest | M6 | Designed |
| C-09 | Session cookie httpOnly + SameSite=Lax, short expiry, server-verified signature; logout clears it | Secure sessions | M1 | Verified |
| C-10 | Pydantic input models with `extra="forbid"`, type coercion, length limits | Input validation | M1 | Verified |
| C-11 | No string SQL; SQLAlchemy bound params; escaped LIKE; sqlglot guard | SQL injection | M1 | Verified |
| C-12 | React escaping; no `dangerouslySetInnerHTML`; CSP; sanitized AI text (M3) | XSS | M1 / M3 | Implemented (React escaping, no raw HTML except the static theme script); CSP pending |
| C-13 | SameSite=Lax + required `X-Requested-With` on state-changing requests; same-origin proxy | CSRF | M1 | Verified |
| C-14 | Rate limiting per user/tenant | Rate limiting | M6 | Not started |
| C-15 | Query timeouts and row caps per tenant policy | Timeouts, resource limits | M1 | Verified |
| C-16 | Audit event for every data access, allowed and denied | Audit logging | M1 | Verified |
| C-17 | Safe errors: code + request id; no SQL, stack traces, paths or secrets | Safe errors | M1 | Verified |
| C-18 | Dependency audits (`pnpm audit`, `pip-audit`); CI later | Dependency checks | M1 manual / M6 CI | Verified manually (0 findings, 2026-10-27); CI in M6 |
| C-19 | Export authorization, metadata header, watermark | Secure export | M4 | Not started |
| C-20 | Configurable retention for audit, chat, disclosure logs | Retention | M5 / M6 | Blocked (Q-014) |
| C-21 | Security headers (CSP, nosniff, Referrer-Policy, frame-ancestors) | XSS / clickjacking | M1 | Verified on API; web has headers but no CSP (ISSUES #9) |
| C-22 | OpenAPI docs disabled in production | Information disclosure | M1 | Implemented (not yet exercised in production mode) |
| C-23 | AI data boundary, disclosure log, provider approval | Minimize AI data | M3 | Designed |
| C-24 | Prompt-injection resistance; planted-payload tests | §10.3 | M3 | Designed |

## Logging rules

- **Never log:** passwords, tokens, cookies, `Authorization` headers, connection strings, query parameter values, result rows, full prompts.
- **May log:** request id, user id, tenant id, route, status, duration, dataset name, field names, row counts, error codes.

## Pre-connection gate (before any real customer connection)

- [ ] Written authorization from Lumiant and the customer, recorded in the session log
- [ ] An approved **test** environment, not production
- [ ] Read-only service account, proven by a write test that fails
- [ ] Credentials supplied through a secret manager or env vars and never committed
- [ ] The customer's AI-provider decision recorded (or AI-off mode chosen)
