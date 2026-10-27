"""Append-only audit trail of data access (allowed and denied). Never stores result or filter values."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from lumiant.core.config import BASE_DIR
from lumiant.core.errors import AppError

log = logging.getLogger("lumiant.audit")


class Base(DeclarativeBase):
    pass


class AuditEvent(Base):
    __tablename__ = "audit_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    request_id: Mapped[str | None] = mapped_column(sa.String(64))
    tenant_id: Mapped[str] = mapped_column(sa.String(64), index=True)
    user_id: Mapped[str] = mapped_column(sa.String(128))
    action: Mapped[str] = mapped_column(sa.String(128))
    dataset: Mapped[str | None] = mapped_column(sa.String(64))
    fields: Mapped[str | None] = mapped_column(sa.String(1000))
    decision: Mapped[str] = mapped_column(sa.String(8))
    reason_code: Mapped[str | None] = mapped_column(sa.String(64))
    row_count: Mapped[int | None]
    duration_ms: Mapped[float | None]
    status: Mapped[str] = mapped_column(sa.String(16))


@dataclass(frozen=True)
class AuditRecord:
    tenant_id: str
    user_id: str
    action: str
    decision: str  # allow | deny
    status: str  # ok | denied | error
    dataset: str | None = None
    fields: tuple[str, ...] = ()
    reason_code: str | None = None
    row_count: int | None = None
    duration_ms: float | None = None
    request_id: str | None = None


class AuditUnavailableError(AppError):
    def __init__(self) -> None:
        super().__init__("audit_unavailable", "The request could not be recorded, so it was not completed.", 503)


def _alembic_config(url: str) -> Config:
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def _ensure_sqlite_dir(url: str) -> None:
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)


def run_migrations(url: str) -> None:
    _ensure_sqlite_dir(url)
    command.upgrade(_alembic_config(url), "head")


class AuditStore:
    def __init__(self, url: str) -> None:
        connect_args: dict[str, Any] = {}
        if url.startswith("sqlite:///"):
            _ensure_sqlite_dir(url)
            connect_args["check_same_thread"] = False
        self.engine = sa.create_engine(url, connect_args=connect_args)
        if url.startswith("sqlite"):

            @sa.event.listens_for(self.engine, "connect")
            def _pragmas(dbapi_conn: Any, _: Any) -> None:
                cur = dbapi_conn.cursor()
                cur.execute("PRAGMA journal_mode=WAL")
                cur.execute("PRAGMA busy_timeout=5000")
                cur.close()

    def record(self, rec: AuditRecord) -> None:
        """Fail closed: if the event cannot be written, the caller must not return data."""
        try:
            with Session(self.engine) as session, session.begin():
                session.add(
                    AuditEvent(
                        occurred_at=datetime.now(UTC),
                        request_id=rec.request_id,
                        tenant_id=rec.tenant_id,
                        user_id=rec.user_id,
                        action=rec.action,
                        dataset=rec.dataset,
                        fields=",".join(rec.fields)[:1000] or None,
                        decision=rec.decision,
                        reason_code=rec.reason_code,
                        row_count=rec.row_count,
                        duration_ms=rec.duration_ms,
                        status=rec.status,
                    )
                )
        except sa.exc.SQLAlchemyError as exc:
            log.error("audit_write_failed", extra={"error_type": type(exc).__name__})
            raise AuditUnavailableError() from exc

    def recent(self, tenant_id: str, limit: int = 50) -> list[AuditEvent]:
        with Session(self.engine) as session:
            stmt = (
                sa.select(AuditEvent)
                .where(AuditEvent.tenant_id == tenant_id)
                .order_by(AuditEvent.id.desc())
                .limit(limit)
            )
            return list(session.scalars(stmt))

    def dispose(self) -> None:
        self.engine.dispose()
