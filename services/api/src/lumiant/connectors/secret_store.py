"""Encrypted store for source connection URLs (V1, docs/05-plan/PRODUCT_V3_PLAN.md §3.4, decision E6).

An administrator can save a tested connection from Admin › Data source instead of editing server environment
variables. The URL (with its credentials) is encrypted with Fernet (AES-128-CBC + HMAC-SHA256) under a master key
from `LUMIANT_SECRET_KEY` before it reaches the application database; without that key, saving is refused and
reading fails closed. It is never returned by any endpoint, logged or audited in clear.

A tenant uses a saved URL when its configuration says `connection: {type: sql, secret_ref: store}`.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import sqlalchemy as sa
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Mapped, Session, mapped_column

from lumiant.audit.store import Base
from lumiant.core.errors import AppError

KEY_ENV = "LUMIANT_SECRET_KEY"


class SourceSecretRow(Base):
    __tablename__ = "source_secret"

    tenant_id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    ciphertext: Mapped[str] = mapped_column(sa.Text())
    backend: Mapped[str] = mapped_column(sa.String(32))
    saved_by: Mapped[str] = mapped_column(sa.String(128))
    saved_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))


def _fernet() -> Fernet | None:
    key = os.environ.get(KEY_ENV, "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError):
        return None


def new_key() -> str:
    """A fresh master key for `LUMIANT_SECRET_KEY` (for setup scripts and docs)."""
    return Fernet.generate_key().decode("ascii")


class SourceSecretStore:
    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine

    @staticmethod
    def available() -> bool:
        return _fernet() is not None

    def save(self, tenant_id: str, url: str, backend: str, saved_by: str) -> dict[str, object]:
        f = _fernet()
        if f is None:
            raise AppError(
                "secret_store_unavailable",
                f"Saving connections needs a master key in {KEY_ENV} on the server. The URL was not stored.",
                409,
            )
        row = SourceSecretRow(
            tenant_id=tenant_id,
            ciphertext=f.encrypt(url.encode("utf-8")).decode("ascii"),
            backend=backend,
            saved_by=saved_by,
            saved_at=datetime.now(UTC),
        )
        with Session(self.engine) as session, session.begin():
            session.merge(row)
        return self.status(tenant_id)

    def status(self, tenant_id: str) -> dict[str, object]:
        with Session(self.engine) as session:
            row = session.get(SourceSecretRow, tenant_id)
            if row is None:
                return {"saved": False, "store_available": self.available()}
            return {
                "saved": True,
                "backend": row.backend,
                "saved_by": row.saved_by,
                "saved_at": row.saved_at.isoformat(),
                "store_available": self.available(),
            }

    def url(self, tenant_id: str) -> str | None:
        """The decrypted URL, or None when nothing is saved or it cannot be decrypted (wrong or missing key)."""
        f = _fernet()
        if f is None:
            return None
        with Session(self.engine) as session:
            row = session.get(SourceSecretRow, tenant_id)
            if row is None:
                return None
            try:
                return f.decrypt(row.ciphertext.encode("ascii")).decode("utf-8")
            except InvalidToken:
                return None

    def delete(self, tenant_id: str) -> bool:
        with Session(self.engine) as session, session.begin():
            row = session.get(SourceSecretRow, tenant_id)
            if row is None:
                return False
            session.delete(row)
            return True
