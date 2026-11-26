"""Admin › Integrations: API keys for service accounts (V3)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lumiant.apikeys.store import GRANTABLE, ApiKeyStore
from lumiant.auth.deps import get_container, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.core.errors import NotFoundError

router = APIRouter(prefix="/api/admin/api-keys", tags=["admin"])
Admin = Annotated[Principal, Depends(require(Permission.ADMIN_TENANT))]
Svc = Annotated[Container, Depends(get_container)]
KeyId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{12}$")]


class NewKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]
    permissions: Annotated[list[str], Field(min_length=1, max_length=10)]
    warehouses: Annotated[
        list[Annotated[str, StringConstraints(min_length=1, max_length=40)]] | None, Field(max_length=200)
    ] = None


@router.get("")
def list_keys(principal: Admin, container: Svc) -> dict[str, Any]:
    keys = ApiKeyStore(container.audit.engine).list(principal.tenant_id)
    return {"keys": keys, "grantable": sorted(p.value for p in GRANTABLE & principal.permissions)}


@router.post("", dependencies=[Depends(require_csrf)])
def create_key(body: NewKey, principal: Admin, container: Svc) -> dict[str, Any]:
    token, record = ApiKeyStore(container.audit.engine).create(principal, body.name, body.permissions, body.warehouses)
    container.query.record(principal, "admin:api_key_create", None, "allow", "ok", reason=str(record["id"]))
    return {"key": token, "record": record, "note": "Copy the key now. It is shown once and cannot be recovered."}


@router.delete("/{key_id}", dependencies=[Depends(require_csrf)])
def revoke_key(key_id: KeyId, principal: Admin, container: Svc) -> dict[str, Any]:
    if not ApiKeyStore(container.audit.engine).revoke(principal.tenant_id, key_id):
        raise NotFoundError("not_found", "No active key with that id.")
    container.query.record(principal, "admin:api_key_revoke", None, "allow", "ok", reason=key_id)
    return {"revoked": key_id}
