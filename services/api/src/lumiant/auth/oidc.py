"""OIDC bearer-token authentication (customer identity provider).

The platform validates tokens issued by the customer's IdP; it never sees passwords. Tokens are expected in
`Authorization: Bearer ...` (typically injected by the customer's gateway / oauth2-proxy). Claims decide the tenant
(issuer + audience) and IdP group membership decides roles and warehouse scope through tenant configuration.

NOT verified against a real IdP (Q-010): it is tested with locally generated keys and a fake JWKS client.
"""

from __future__ import annotations

import logging
from typing import Any

import jwt

from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal, WarehouseScope
from lumiant.core.errors import ForbiddenError, NotAuthenticatedError
from lumiant.tenancy.models import TenantConfig
from lumiant.tenancy.registry import TenantRegistry

log = logging.getLogger("lumiant.auth.oidc")
# Asymmetric algorithms only: never "none", never HMAC (which enables key-confusion attacks).
ALGORITHMS = ["RS256", "RS384", "RS512", "PS256", "ES256", "ES384"]


def _default_jwks_client(url: str) -> Any:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600, timeout=5)


class OidcAuthProvider:
    def __init__(self, tenants: TenantRegistry) -> None:
        self._configs: dict[tuple[str, str], TenantConfig] = {}
        for cfg in tenants:
            if cfg.oidc is not None:
                self._configs[(cfg.oidc.issuer, cfg.oidc.audience)] = cfg
        if not self._configs:
            raise RuntimeError("LUMIANT_AUTH_MODE=oidc needs at least one tenant with an 'oidc' configuration")
        self._clients: dict[str, Any] = {}

    def _client(self, url: str) -> Any:
        if url not in self._clients:
            self._clients[url] = _default_jwks_client(url)
        return self._clients[url]

    def _tenant_for(self, token: str) -> TenantConfig:
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
        except jwt.PyJWTError as exc:
            raise NotAuthenticatedError("Your session is invalid or has expired. Sign in again.") from exc
        issuer = claims.get("iss")
        audiences = claims.get("aud")
        for aud in [audiences] if isinstance(audiences, str) else list(audiences or []):
            cfg = self._configs.get((str(issuer), str(aud)))
            if cfg is not None:
                return cfg
        raise NotAuthenticatedError("Your session is invalid or has expired. Sign in again.")

    def authenticate(self, token: str) -> Principal:
        cfg = self._tenant_for(token)
        oidc = cfg.oidc
        assert oidc is not None
        try:
            key = self._client(oidc.jwks_url).get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=ALGORITHMS,
                audience=oidc.audience,
                issuer=oidc.issuer,
                leeway=30,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as exc:
            log.info("oidc_token_rejected", extra={"error_type": type(exc).__name__})
            raise NotAuthenticatedError("Your session is invalid or has expired. Sign in again.") from exc
        except Exception as exc:  # JWKS fetch failures etc.: treat as unauthenticated, never leak details
            log.warning("oidc_verification_failed", extra={"error_type": type(exc).__name__})
            raise NotAuthenticatedError("Your session could not be verified. Try again shortly.") from exc

        raw_groups = claims.get(oidc.groups_claim, [])
        groups = [raw_groups] if isinstance(raw_groups, str) else [str(g) for g in raw_groups or []]
        roles = list(dict.fromkeys(oidc.group_roles[g] for g in groups if g in oidc.group_roles))
        if not roles:
            raise ForbiddenError("no_access", "Your account is not assigned to any role for this application.")
        permissions: set[Permission] = set()
        for role in roles:
            permissions.update(cfg.roles.get(role, []))
        all_wh = False
        ids: set[str] = set()
        for g in groups:
            scope = oidc.group_scopes.get(g)
            if scope is None:
                continue
            ids.update(cfg.warehouses_of_departments(scope.departments))
            for w in scope.warehouses:
                if w == "*":
                    all_wh = True
                else:
                    ids.add(w)
        if all_wh:
            ids = {w.id for w in cfg.warehouses}
        user = str(claims.get(oidc.username_claim) or claims["sub"])
        name = str(claims.get(oidc.name_claim) or user)
        return Principal(
            user, name, cfg.id, tuple(roles), frozenset(permissions), WarehouseScope(all_wh, frozenset(ids))
        )
