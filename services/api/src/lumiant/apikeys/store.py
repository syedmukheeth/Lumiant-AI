"""API keys for service accounts (V3, docs/05-plan/PRODUCT_V3_PLAN.md §4): the public API, the MCP server and other
integrations sign in with a key instead of a browser session.

- A key is shown once, at creation. Only its SHA-256 hash is stored (keys are 256-bit random, so a plain hash is
  enough); a key cannot be recovered, only revoked and replaced.
- A key can never do more than the administrator who created it: its permissions are a subset of the creator's,
  without administration or audit rights, and its warehouse scope is inside the creator's.
- Every request made with a key is audited as `apikey:<id>`.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, Session, mapped_column

from lumiant.audit.store import Base
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal, WarehouseScope
from lumiant.core.errors import AppError, NotAuthenticatedError

PREFIX = "lmk_"
# What a key may be given; administration and the audit log stay with people.
GRANTABLE = frozenset(
    {
        Permission.DASHBOARD_READ,
        Permission.INVENTORY_READ,
        Permission.COST_READ,
        Permission.QUERY_RUN,
        Permission.CHAT_USE,
        Permission.EXPORT_DATA,
    }
)
_TOUCH_EVERY = timedelta(minutes=1)


class ApiKeyRow(Base):
    __tablename__ = "api_key"

    id: Mapped[str] = mapped_column(sa.String(24), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(sa.String(64), index=True)
    name: Mapped[str] = mapped_column(sa.String(80))
    secret_hash: Mapped[str] = mapped_column(sa.String(64))
    permissions: Mapped[str] = mapped_column(sa.String(400))
    scope_all: Mapped[bool] = mapped_column(sa.Boolean())
    warehouses: Mapped[str] = mapped_column(sa.String(2000))
    created_by: Mapped[str] = mapped_column(sa.String(128))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _public(row: ApiKeyRow) -> dict[str, object]:
    return {
        "id": row.id,
        "name": row.name,
        "permissions": sorted(p for p in row.permissions.split(",") if p),
        "warehouses": "all" if row.scope_all else sorted(w for w in row.warehouses.split(",") if w),
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
        "revoked": row.revoked_at is not None,
    }


class ApiKeyStore:
    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine

    def create(
        self, creator: Principal, name: str, permissions: list[str], warehouses: list[str] | None
    ) -> tuple[str, dict[str, object]]:
        """A new key for the creator's tenant. Returns (the key, shown once; its public record)."""
        try:
            wanted = {Permission(p) for p in permissions}
        except ValueError as exc:
            raise AppError("invalid_request", "Unknown permission.", 422) from exc
        if not wanted:
            raise AppError("invalid_request", "Give the key at least one permission.", 422)
        if not wanted <= (GRANTABLE & creator.permissions):
            raise AppError("forbidden", "A key cannot have rights its creator lacks, or administration rights.", 403)
        if warehouses is None:
            scope_all, ids = creator.scope.all, sorted(creator.scope.ids)
        else:
            if not warehouses or not all(creator.scope.allows(w) for w in warehouses):
                raise AppError("forbidden_scope", "A key's warehouses must be inside your own scope.", 403)
            scope_all, ids = False, sorted(set(warehouses))
        key_id = uuid.uuid4().hex[:12]
        secret = secrets.token_urlsafe(32)
        row = ApiKeyRow(
            id=key_id,
            tenant_id=creator.tenant_id,
            name=name,
            secret_hash=_hash(secret),
            permissions=",".join(sorted(p.value for p in wanted)),
            scope_all=scope_all,
            warehouses=",".join(ids),
            created_by=creator.user_id,
            created_at=datetime.now(UTC),
            last_used_at=None,
            revoked_at=None,
        )
        with Session(self.engine) as session, session.begin():
            session.add(row)
            session.flush()
            record = _public(row)
        return f"{PREFIX}{key_id}_{secret}", record

    def list(self, tenant_id: str) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            rows = session.scalars(
                sa.select(ApiKeyRow).where(ApiKeyRow.tenant_id == tenant_id).order_by(ApiKeyRow.created_at.desc())
            ).all()
            return [_public(r) for r in rows]

    def revoke(self, tenant_id: str, key_id: str) -> bool:
        with Session(self.engine) as session, session.begin():
            row = session.get(ApiKeyRow, key_id)
            if row is None or row.tenant_id != tenant_id or row.revoked_at is not None:
                return False
            row.revoked_at = datetime.now(UTC)
            return True

    def authenticate(self, token: str, tenant_exists: object) -> Principal:
        """The principal a key acts as. Any problem is the same 401, so a caller learns nothing about keys."""
        if not token.startswith(PREFIX):
            raise NotAuthenticatedError()
        key_id, _, secret = token[len(PREFIX) :].partition("_")
        if not key_id or not secret:
            raise NotAuthenticatedError()
        with Session(self.engine) as session, session.begin():
            row = session.get(ApiKeyRow, key_id)
            if row is None or row.revoked_at is not None or not hmac.compare_digest(row.secret_hash, _hash(secret)):
                raise NotAuthenticatedError()
            if callable(tenant_exists) and not tenant_exists(row.tenant_id):
                raise NotAuthenticatedError()
            now = datetime.now(UTC)
            last = row.last_used_at
            if last is None or now - (last if last.tzinfo else last.replace(tzinfo=UTC)) > _TOUCH_EVERY:
                row.last_used_at = now
            return Principal(
                user_id=f"apikey:{row.id}",
                display_name=row.name,
                tenant_id=row.tenant_id,
                roles=("api_key",),
                permissions=frozenset(Permission(p) for p in row.permissions.split(",") if p),
                scope=WarehouseScope(row.scope_all, frozenset(w for w in row.warehouses.split(",") if w)),
            )
