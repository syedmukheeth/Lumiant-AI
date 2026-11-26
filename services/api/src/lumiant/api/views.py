"""Saved views (V4): a person names the filters and sort of a page and comes back to them on any device.

A view is only the page's query string (filters, search, sort), validated against the keys that page accepts; it holds
no data and grants nothing: opening it runs the page's normal, scoped queries. Views are private to their owner.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy.orm import Mapped, Session, mapped_column

from lumiant.audit.store import Base
from lumiant.auth.deps import current_principal, get_container, require_csrf
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.core.errors import AppError, NotFoundError

router = APIRouter(prefix="/api/views", tags=["views"])
Who = Annotated[Principal, Depends(current_principal)]
Svc = Annotated[Container, Depends(get_container)]
# The query keys each page understands; anything else is dropped before saving.
PAGES: dict[str, frozenset[str]] = {
    "inventory": frozenset({"warehouse", "item_group", "abc", "stage", "status", "q", "sort", "dir"}),
}
MAX_VIEWS = 50


class SavedViewRow(Base):
    __tablename__ = "saved_view"

    id: Mapped[str] = mapped_column(sa.String(24), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(sa.String(64))
    user_id: Mapped[str] = mapped_column(sa.String(128), index=True)
    page: Mapped[str] = mapped_column(sa.String(40))
    name: Mapped[str] = mapped_column(sa.String(80))
    query: Mapped[str] = mapped_column(sa.String(1000))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))


class NewView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: Annotated[str, StringConstraints(pattern=r"^[a-z_]{1,40}$")]
    name: Annotated[str, StringConstraints(min_length=1, max_length=80, strip_whitespace=True)]
    query: Annotated[str, StringConstraints(max_length=1000)]


def _clean(page: str, query: str) -> str:
    allowed = PAGES.get(page)
    if allowed is None:
        raise AppError("invalid_request", "Views cannot be saved for that page.", 422)
    pairs = [(k, v[:200]) for k, v in parse_qsl(query.lstrip("?"), keep_blank_values=False) if k in allowed]
    return urlencode(pairs)


def _public(r: SavedViewRow) -> dict[str, Any]:
    return {"id": r.id, "page": r.page, "name": r.name, "query": r.query, "created_at": r.created_at.isoformat()}


@router.get("")
def list_views(
    principal: Who, container: Svc, page: Annotated[str, Query(pattern=r"^[a-z_]{1,40}$")]
) -> dict[str, Any]:
    with Session(container.audit.engine) as session:
        rows = session.scalars(
            sa.select(SavedViewRow)
            .where(
                SavedViewRow.tenant_id == principal.tenant_id,
                SavedViewRow.user_id == principal.user_id,
                SavedViewRow.page == page,
            )
            .order_by(SavedViewRow.name)
        ).all()
        return {"views": [_public(r) for r in rows]}


@router.post("", dependencies=[Depends(require_csrf)])
def save_view(body: NewView, principal: Who, container: Svc) -> dict[str, Any]:
    query = _clean(body.page, body.query)
    with Session(container.audit.engine) as session, session.begin():
        count = session.scalar(
            sa.select(sa.func.count()).where(
                SavedViewRow.tenant_id == principal.tenant_id, SavedViewRow.user_id == principal.user_id
            )
        )
        if (count or 0) >= MAX_VIEWS:
            raise AppError("too_many_views", f"You can keep up to {MAX_VIEWS} saved views. Delete one first.", 409)
        row = SavedViewRow(
            id=uuid.uuid4().hex[:12],
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            page=body.page,
            name=body.name,
            query=query,
            created_at=datetime.now(UTC),
        )
        session.add(row)
        session.flush()
        return _public(row)


@router.delete("/{view_id}", dependencies=[Depends(require_csrf)])
def delete_view(
    view_id: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{12}$")], principal: Who, container: Svc
) -> dict[str, Any]:
    with Session(container.audit.engine) as session, session.begin():
        row = session.get(SavedViewRow, view_id)
        if row is None or row.user_id != principal.user_id or row.tenant_id != principal.tenant_id:
            raise NotFoundError("not_found", "No saved view with that id.")
        session.delete(row)
    return {"deleted": view_id}
