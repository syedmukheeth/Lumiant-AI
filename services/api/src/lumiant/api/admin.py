from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lumiant.analyses import cache
from lumiant.auth.deps import get_container, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.connectors.probe import probe, suggest_for_url
from lumiant.connectors.secret_store import SourceSecretStore
from lumiant.container import Container
from lumiant.core.errors import AppError

router = APIRouter(prefix="/api/admin", tags=["admin"])
Admin = Annotated[Principal, Depends(require(Permission.ADMIN_TENANT))]
AuditReader = Annotated[Principal, Depends(require(Permission.AUDIT_READ))]
Reconciler = Annotated[Principal, Depends(require(Permission.ADMIN_TENANT, Permission.COST_READ))]
Svc = Annotated[Container, Depends(get_container)]
Short = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class ReconRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    warehouse_id: Short
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Za-z]{3}$")]
    value: Annotated[str, StringConstraints(min_length=1, max_length=40)]


class ReconRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tolerance: Annotated[str, StringConstraints(max_length=20)] = "0.01"
    rows: Annotated[list[ReconRow], Field(min_length=1, max_length=500)]


@router.get("/schema")
def schema(principal: Admin, container: Svc) -> dict[str, Any]:
    return container.admin.discovery(principal)


@router.get("/source")
def source(principal: Admin, container: Svc) -> dict[str, Any]:
    return container.admin.source(principal)


class ProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: Annotated[str, StringConstraints(min_length=8, max_length=2000)]


@router.post("/source/test", dependencies=[Depends(require_csrf)])
def test_source(body: ProbeRequest, principal: Admin, container: Svc) -> dict[str, Any]:
    """Try a connection URL before it is configured. The URL is used once: never stored, logged or returned."""
    result = probe(body.url, allow_sqlite=not container.settings.is_production)
    container.query.record(
        principal, "admin:source_test", None, "allow", "ok" if result["ok"] else "error", reason=result.get("code")
    )
    return result


@router.get("/source/saved")
def saved_source(principal: Admin, container: Svc) -> dict[str, Any]:
    tenant = container.tenants.get(principal.tenant_id)
    status = SourceSecretStore(container.audit.engine).status(principal.tenant_id)
    return {**status, "in_use": tenant.connection.type == "sql" and tenant.connection.secret_ref == "store"}  # noqa: S105 (a reference name, not a secret)


@router.post("/source/save", dependencies=[Depends(require_csrf)])
def save_source(body: ProbeRequest, principal: Admin, container: Svc) -> dict[str, Any]:
    """Test, then store the URL encrypted for this workspace. Refused when the account can write."""
    checked = probe(body.url, allow_sqlite=not container.settings.is_production)
    if not checked["ok"]:
        container.query.record(principal, "admin:source_save", None, "allow", "error", reason=checked.get("code"))
        return checked
    if checked["read_only"]["status"] == "writable":
        container.query.record(principal, "admin:source_save", None, "deny", "denied", reason="writable_account")
        raise AppError(
            "writable_account", "This account can change data. Save a connection for a read-only account.", 409
        )
    status = SourceSecretStore(container.audit.engine).save(
        principal.tenant_id, body.url, str(checked["backend"]), principal.user_id
    )
    container.connectors.forget(principal.tenant_id)
    cache.clear(container.query)
    container.query.record(principal, "admin:source_save", None, "allow", "ok", reason=str(checked["backend"]))
    return {"ok": True, **status}


@router.post("/source/suggest", dependencies=[Depends(require_csrf)])
def suggest_for_source(body: ProbeRequest, principal: Admin, container: Svc) -> dict[str, Any]:
    """Mapping suggestions for a source that is not configured yet: table and column names only, URL used once."""
    result = suggest_for_url(body.url, allow_sqlite=not container.settings.is_production)
    container.query.record(
        principal, "admin:source_suggest", None, "allow", "ok" if result["ok"] else "error", reason=result.get("code")
    )
    return result


@router.get("/mapping/suggest")
def suggest_mapping(principal: Admin, container: Svc) -> dict[str, Any]:
    return container.admin.suggest_mapping(principal)


@router.get("/validation")
def validation(principal: Admin, container: Svc) -> dict[str, Any]:
    return container.admin.validation(principal)


@router.get("/capabilities")
def capabilities(principal: Admin, container: Svc) -> dict[str, Any]:
    return {"capabilities": container.admin.capabilities(principal)}


@router.get("/audit")
def audit(
    principal: AuditReader,
    container: Svc,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0, le=100_000)] = 0,
    decision: Annotated[str | None, Query(pattern=r"^(allow|deny)$")] = None,
    action: Annotated[str | None, Query(max_length=40, pattern=r"^[A-Za-z0-9_:.-]*$")] = None,
) -> dict[str, Any]:
    return {
        "events": container.admin.audit(principal, limit=limit, offset=offset, decision=decision, prefix=action or None)
    }


@router.post("/reconciliation", dependencies=[Depends(require_csrf)])
def reconciliation(body: ReconRequest, principal: Reconciler, container: Svc) -> dict[str, Any]:
    return container.admin.reconcile(principal, [r.model_dump() for r in body.rows], body.tolerance)
