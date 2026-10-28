"""Authentication providers (ADR-0004). M1 ships only the development provider."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt

from lumiant.auth.principal import Principal, principal_for_dev_user
from lumiant.core.config import Settings
from lumiant.core.errors import NotAuthenticatedError
from lumiant.tenancy.models import TenantConfig
from lumiant.tenancy.registry import TenantRegistry

COOKIE_NAME = "lumiant_session"
_ISSUER = "lumiant-dev"
_AUDIENCE = "lumiant-api"


class DevAuthProvider:
    """Signed-cookie sessions for the dev users declared in synthetic tenant configs. Never for production.

    The token carries only the username and tenant; roles and scope are re-resolved from the tenant
    config on every request, so permission changes apply immediately. Customer-extract tenants (real client
    files, ADR-0008) are reachable only in development with LUMIANT_ALLOW_CUSTOMER_EXTRACTS=true.
    """

    def __init__(self, settings: Settings, tenants: TenantRegistry) -> None:
        if not settings.dev_auth_enabled:
            raise RuntimeError("development authentication is disabled in this environment")
        configured = settings.dev_jwt_secret
        self._secret = configured.get_secret_value() if configured else secrets.token_urlsafe(48)
        self._ttl = timedelta(minutes=settings.session_ttl_minutes)
        self._tenants = tenants
        self._extracts_allowed = settings.customer_extract_login_allowed

    def _login_allowed(self, tenant: TenantConfig) -> bool:
        return tenant.synthetic or (tenant.customer_extract and self._extracts_allowed)

    @property
    def ttl_seconds(self) -> int:
        return int(self._ttl.total_seconds())

    def users(self) -> list[dict[str, object]]:
        listing: list[dict[str, object]] = []
        for tenant in self._tenants:
            if not self._login_allowed(tenant):
                continue
            for user in tenant.dev_users:
                listing.append(
                    {
                        "username": user.username,
                        "display_name": user.display_name,
                        "tenant_id": tenant.id,
                        "tenant_name": tenant.display_name,
                        "roles": user.roles,
                        "data_classification": tenant.data_classification,
                    }
                )
        return listing

    def issue(self, username: str) -> tuple[str, Principal]:
        found = self._tenants.find_dev_user(username)
        if found is None or not self._login_allowed(found[0]):
            raise NotAuthenticatedError("Unknown development user.")
        tenant, user = found
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": user.username,
                "tid": tenant.id,
                "iss": _ISSUER,
                "aud": _AUDIENCE,
                "iat": now,
                "exp": now + self._ttl,
                "jti": secrets.token_hex(8),
            },
            self._secret,
            algorithm="HS256",
        )
        return token, principal_for_dev_user(tenant, user)

    def authenticate(self, token: str) -> Principal:
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience=_AUDIENCE,
                issuer=_ISSUER,
                options={"require": ["exp", "iat", "sub", "tid", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise NotAuthenticatedError("Your session is invalid or has expired. Sign in again.") from exc
        found = self._tenants.find_dev_user(str(claims["sub"]))
        if found is None or found[0].id != claims["tid"] or not self._login_allowed(found[0]):
            raise NotAuthenticatedError("Your session is no longer valid. Sign in again.")
        return principal_for_dev_user(*found)
