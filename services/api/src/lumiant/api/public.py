"""Public endpoints used by the landing page (no session). Nothing here reads tenant data."""

from __future__ import annotations

import logging
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator

from lumiant.auth.deps import get_container, rate_limit_by_ip, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.core.errors import AppError, ForbiddenError
from lumiant.leads.store import DemoRequest, DemoRequestStore

log = logging.getLogger("lumiant.leads")
router = APIRouter(tags=["public"])

_EMAIL = re.compile(r"^[^@\s<>]{1,64}@[A-Za-z0-9.-]{1,185}\.[A-Za-z]{2,24}$")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = _CONTROL.sub("", value).strip()
    return text or None


class DemoRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    company: str = Field(min_length=1, max_length=160)
    role: str | None = Field(default=None, max_length=120)
    systems: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=1000)
    consent: bool
    # Hidden field: people never fill it; simple form bots do. Accepted and dropped silently.
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name", "company", "role", "systems", "message", mode="after")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return _clean(v)

    @field_validator("email", mode="after")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL.match(v):
            raise ValueError("enter a valid work email address")
        return v.lower()


@router.post(
    "/api/public/demo-requests",
    status_code=202,
    dependencies=[Depends(require_csrf), Depends(rate_limit_by_ip("login"))],
)
def create_demo_request(
    body: DemoRequestBody,
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, str]:
    if not body.consent:
        raise AppError("consent_required", "Please agree to be contacted about the demo.", 422)
    if body.website:
        log.info("demo_request_dropped", extra={"reason": "honeypot"})
        return {"status": "received"}
    if not body.name or not body.company:
        raise AppError("invalid_request", "Name and company are required.", 422)
    DemoRequestStore(container.audit.engine).add(
        DemoRequest(body.name, body.email, body.company, body.role, body.systems, body.message)
    )
    log.info("demo_request_received")  # no personal details in logs
    return {"status": "received"}


PlatformAdmin = Annotated[Principal, Depends(require(Permission.ADMIN_TENANT, Permission.AUDIT_READ))]


@router.get("/api/admin/demo-requests")
def list_demo_requests(
    principal: PlatformAdmin,
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    # Demo requests are platform data, not tenant data: only platform administrators may read them.
    if "super_admin" not in principal.roles:
        raise ForbiddenError("forbidden", "Only platform administrators can view demo requests.")
    return {"requests": DemoRequestStore(container.audit.engine).recent(100)}
