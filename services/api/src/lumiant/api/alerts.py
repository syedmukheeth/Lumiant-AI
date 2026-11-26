"""Admin › Integrations: alert rules that push findings to a signed webhook (V3)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lumiant.alerts.service import AlertService
from lumiant.auth.deps import get_container, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.core.errors import NotFoundError

router = APIRouter(prefix="/api/admin/alerts", tags=["admin"])
Admin = Annotated[Principal, Depends(require(Permission.ADMIN_TENANT))]
Svc = Annotated[Container, Depends(get_container)]
RuleId = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{12}$")]


class NewRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]
    url: Annotated[str, StringConstraints(min_length=8, max_length=500)]
    min_severity: Annotated[str, StringConstraints(pattern=r"^(info|warning|critical)$")] = "warning"
    every_hours: Annotated[int | None, Field(ge=1, le=24 * 7)] = None  # sent by `lumiant-alerts send-due`


def _local(container: Container) -> bool:
    return not container.settings.is_production


@router.get("")
def list_rules(principal: Admin, container: Svc) -> dict[str, Any]:
    return {"rules": AlertService(container.audit.engine).list_rules(principal.tenant_id)}


@router.post("", dependencies=[Depends(require_csrf)])
def create_rule(body: NewRule, principal: Admin, container: Svc) -> dict[str, Any]:
    secret, record = AlertService(container.audit.engine).create(
        principal,
        body.name,
        body.url,
        body.min_severity,
        allow_local=_local(container),
        every_hours=body.every_hours,
    )
    container.query.record(principal, "admin:alert_create", None, "allow", "ok", reason=str(record["id"]))
    return {
        "secret": secret,
        "record": record,
        "note": "Copy the signing secret now; it is shown once. Verify X-Lumiant-Signature with it.",
    }


@router.post("/{rule_id}/send", dependencies=[Depends(require_csrf)])
def send_now(rule_id: RuleId, principal: Admin, container: Svc) -> dict[str, Any]:
    """Compute the findings now (your scope and rights) and deliver them to the rule's webhook."""
    feed = container.insights.feed(principal, fresh=True)
    result = AlertService(container.audit.engine).send(
        principal.tenant_id, rule_id, feed, allow_local=_local(container)
    )
    container.query.record(
        principal, "admin:alert_send", None, "allow", "ok" if result["ok"] else "error", reason=rule_id
    )
    return result


@router.delete("/{rule_id}", dependencies=[Depends(require_csrf)])
def delete_rule(rule_id: RuleId, principal: Admin, container: Svc) -> dict[str, Any]:
    if not AlertService(container.audit.engine).delete(principal.tenant_id, rule_id):
        raise NotFoundError("not_found", "No alert rule with that id.")
    container.query.record(principal, "admin:alert_delete", None, "allow", "ok", reason=rule_id)
    return {"deleted": rule_id}
