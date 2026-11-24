# Production Authentication

_23 Nov 2026. Status: **implemented, unverified against a real identity provider** (blocked on a customer IdP tenant)._

## Model: identity-aware gateway + OIDC bearer validation

```
browser ──► customer gateway (oauth2-proxy / Azure App Proxy / Cloudflare Access …)
              │  OIDC code flow + PKCE, session cookie held by the gateway
              ▼  forwards Authorization: Bearer <access or id token>
            web (Next.js)  ── /api/* rewrite (same origin) ──►  API (FastAPI)
                                                                 └─ validates the token on EVERY request:
                                                                    issuer, audience, signature via JWKS, expiry,
                                                                    alg allow-list (no none / HS confusion),
                                                                    groups claim → roles + warehouse scope
```

| Piece | Where | Status |
|---|---|---|
| Token validation, tenant from issuer, group → role and scope mapping | `services/api/src/lumiant/auth/oidc.py`, `auth/deps.py` `current_principal` | Verified with local keys (`test_oidc.py`), incl. `alg:none` and algorithm confusion rejected |
| Dev auth refused in production | `core/config.py` validator (`auth_mode=dev` with `app_env=production` fails at startup) | Verified (`test_config.py`) |
| **Web routing in OIDC mode** (LA-01) | `apps/web/src/proxy.ts` `needsDevLogin`: with `LUMIANT_AUTH_MODE=oidc` the web app no longer redirects to the dev sign-in page; the gateway signs users in | **Fixed 23 Nov**; unit test `tests/unit/proxy.test.ts` |
| Gateway in front of web and API | customer infrastructure | **Blocked**: needs the customer IdP and gateway |
| Session revocation (LA-12) | gateway session plus short token lifetime | Configuration at the gateway; dev cookies remain non-revocable until expiry (dev only) |

## Deployment settings (production)

API:
- `LUMIANT_APP_ENV=production`
- `LUMIANT_AUTH_MODE=oidc`
- `LUMIANT_COOKIE_SECURE=true`
- OIDC issuer, audience and JWKS per tenant in the tenant YAML (`auth.oidc`), with group → role and warehouse mappings.

Web:
- `LUMIANT_AUTH_MODE=oidc`, set at build **and** runtime;
- `LUMIANT_API_ORIGIN`.

Gateway: route both the web origin and `/api/*` through it, require authentication for all paths, forward `Authorization: Bearer`, and set a session lifetime that matches policy.

## Not yet done

- **Built-in OIDC flow without a gateway:** a backend-for-frontend with code + PKCE and server-side sessions. This is optional when a gateway is used, and planned for customers without one.
- **SAML:** supported through the gateway (most gateways accept SAML IdPs and emit OIDC tokens). There is no direct SAML in the API.
- **Sign-out in OIDC mode** should call the gateway's sign-out URL. Today the UI's sign-out clears only the dev cookie.
- **End-to-end test** against a real IdP, for example a Keycloak container in CI, is the next step to move from "implemented" to "verified".
