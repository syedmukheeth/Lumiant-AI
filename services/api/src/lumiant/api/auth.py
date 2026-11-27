from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, StringConstraints

from lumiant.auth.deps import current_principal, get_container, rate_limit_by_ip, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.auth.provider import COOKIE_NAME
from lumiant.container import Container
from lumiant.core.errors import NotFoundError

router = APIRouter(prefix="/api/auth", tags=["auth"])

SECTIONS = (
    ("overview", Permission.DASHBOARD_READ),
    ("inventory", Permission.INVENTORY_READ),
    ("risks", Permission.INVENTORY_READ),
    ("costs", Permission.COST_READ),
    ("assistant", Permission.CHAT_USE),
    ("reports", Permission.INVENTORY_READ),
    ("admin", Permission.ADMIN_TENANT),
)


class DevLogin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")]


def planning_sections(principal: Principal, container: Container) -> list[str]:
    """Planning pages appear only when the role allows them AND the tenant provides the data they need, so a
    module is never offered where it could only show an error. The endpoints check the same rules server-side."""
    mapping = container.query.mapping(principal.tenant_id)
    out: list[str] = []
    if principal.has(Permission.INVENTORY_READ) and (
        mapping.is_mapped("customer_order_line") or mapping.is_mapped("bom_component")
    ):
        out.append("planning")
    if principal.has(Permission.COST_READ) and mapping.is_mapped("supplier_item"):
        out.append("procurement")
    if principal.has(Permission.INVENTORY_READ):
        out.append("master_data")
    return out


def me_payload(principal: Principal, container: Container) -> dict[str, Any]:
    tenant = container.tenants.get(principal.tenant_id)
    names = {w.id: w for w in tenant.warehouses}
    return {
        "user": {"id": principal.user_id, "display_name": principal.display_name},
        "tenant": {"id": tenant.id, "display_name": tenant.display_name},
        "roles": list(principal.roles),
        "permissions": sorted(p.value for p in principal.permissions),
        "scope": {
            **principal.scope.summary(),
            "departments": sorted({names[w].department for w in principal.scope.ids if w in names}),
        },
        "sections": [name for name, perm in SECTIONS if principal.has(perm)] + planning_sections(principal, container),
        "auth_mode": container.settings.auth_mode.value,
    }


def _dev_auth(container: Container) -> Any:
    if container.dev_auth is None:
        raise NotFoundError()
    return container.dev_auth


@router.get("/dev-users")
def dev_users(container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    return {"users": _dev_auth(container).users(), "notice": "Development authentication, not for production."}


@router.post("/dev-login", dependencies=[Depends(require_csrf), Depends(rate_limit_by_ip("login"))])
def dev_login(body: DevLogin, response: Response, container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    provider = _dev_auth(container)
    token, principal = provider.issue(body.username)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=provider.ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=container.settings.cookie_secure,
        path="/",
    )
    container.query.record(principal, "auth.dev_login", None, "allow", "ok")
    return me_payload(principal, container)


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "signed_out"}


@router.get("/me")
def me(
    principal: Principal = Depends(current_principal),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    return me_payload(principal, container)
