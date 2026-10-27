# ADR-0004: Development-only authentication mode with a hard production guard

- **Status:** Accepted
- **Date:** 2026-10-26
- **Session:** S01
- **Related:** brief §20 Phase 3; NFR-007; Q-010

## Context
The customer IdP is unknown (Q-010). We need authenticated principals now to build and test RBAC, scope and tenant isolation. The brief requires that development authentication can never be used accidentally in production.

## Decision
- `AuthProvider` interface; M1 ships `DevAuthProvider`: a user picker of `dev_users` from tenant YAML; FastAPI issues an HS256-signed JWT (8 h) in an httpOnly, SameSite=Lax cookie (`Secure` when served over HTTPS).
- Settings validation **fails startup** when `LUMIANT_AUTH_MODE=dev` and `LUMIANT_APP_ENV=production`. Dev endpoints return 404 when not in dev mode. Tests cover both.
- If no `LUMIANT_DEV_JWT_SECRET` is set in dev, a random secret is generated per process (sessions reset on restart).
- The UI labels the login page "Development authentication — not for production".
- M6 adds `OidcAuthProvider` (validate IdP tokens via JWKS; map groups → roles).

## Consequences
- + RBAC, scope and isolation are real and testable today.
- − Dev users are config, not a user store; acceptable for synthetic tenants only.

## Alternatives considered
- Hardcoded header-based identity: trivially spoofable, easy to leak into prod.
- Local username/password store: we'd build credential storage we'll throw away; customers will use SSO.

## Revisit when
Customer IdP is confirmed (Q-010).
