from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lumiant.auth.deps import get_container, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container

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
