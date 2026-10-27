"""FastAPI dependencies: authentication, permission checks, CSRF header. Every data route uses these."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, Request

from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.auth.provider import COOKIE_NAME
from lumiant.container import Container
from lumiant.core.errors import ForbiddenError, NotAuthenticatedError
from lumiant.core.logging import tenant_id_var, user_id_var

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "lumiant"


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


def current_principal(request: Request, container: Container = Depends(get_container)) -> Principal:  # noqa: B008
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


def require_csrf(request: Request) -> None:
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise ForbiddenError("csrf_failed", "This request is missing a required header.")
