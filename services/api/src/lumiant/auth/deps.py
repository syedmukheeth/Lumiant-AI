"""FastAPI dependencies: authentication, permission checks, CSRF header. Every data route uses these."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, Request

from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.auth.provider import COOKIE_NAME
from lumiant.container import Container
from lumiant.core.errors import AppError, ForbiddenError, NotAuthenticatedError
from lumiant.core.logging import tenant_id_var, user_id_var

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "lumiant"


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def current_principal(request: Request, container: Container = Depends(get_container)) -> Principal:  # noqa: B008
    if container.oidc is not None:
        header = request.headers.get("authorization", "")
        scheme, _, bearer = header.partition(" ")
        if scheme.lower() != "bearer" or not bearer.strip():
            raise NotAuthenticatedError()
        principal = container.oidc.authenticate(bearer.strip())
    else:
        token = request.cookies.get(COOKIE_NAME)
        if not token or container.dev_auth is None:
            raise NotAuthenticatedError()
        principal = container.dev_auth.authenticate(token)
    user_id_var.set(principal.user_id)
    tenant_id_var.set(principal.tenant_id)
    return principal


def require(*permissions: Permission) -> Callable[..., Principal]:
    def dependency(
        request: Request,
        principal: Principal = Depends(current_principal),  # noqa: B008
        container: Container = Depends(get_container),  # noqa: B008
    ) -> Principal:
        missing = [p for p in permissions if not principal.has(p)]
        if missing:
            container.query.record(
                principal, f"{request.method} {request.url.path}", None, "deny", "denied", reason="missing_permission"
            )
            raise ForbiddenError("forbidden", "Your role does not allow this.")
        return principal

    return dependency


def _limit(settings: Any, bucket: str) -> int:
    return {  # type: ignore[no-any-return]
        "chat": settings.rate_limit_chat_per_min,
        "query": settings.rate_limit_query_per_min,
        "export": settings.rate_limit_export_per_min,
        "login": settings.rate_limit_login_per_min,
    }[bucket]


def _enforce(container: Container, bucket: str, who: str) -> None:
    if not container.settings.rate_limit_enabled:
        return
    allowed, retry = container.limiter.hit(f"{bucket}:{who}", _limit(container.settings, bucket), 60.0)
    if not allowed:
        raise AppError(
            "rate_limited", "Too many requests. Please wait a moment and try again.", 429, {"Retry-After": str(retry)}
        )


def rate_limit(bucket: str) -> Callable[..., None]:
    """Per-user limit for authenticated endpoints."""

    def dependency(
        principal: Principal = Depends(current_principal),  # noqa: B008
        container: Container = Depends(get_container),  # noqa: B008
    ) -> None:
        _enforce(container, bucket, f"{principal.tenant_id}:{principal.user_id}")

    return dependency


def rate_limit_by_ip(bucket: str) -> Callable[..., None]:
    """Per-client-address limit for unauthenticated endpoints such as sign-in."""

    def dependency(request: Request, container: Container = Depends(get_container)) -> None:  # noqa: B008
        _enforce(container, bucket, request.client.host if request.client else "unknown")

    return dependency


def require_csrf(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise ForbiddenError("csrf_failed", "This request is missing a required header.")
