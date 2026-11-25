"""Storage for demo requests sent from the public landing page.

These are personal details a visitor typed (name, work email, company), stored only to arrange a demo. They live in
the application database beside the audit log, are never mixed with tenant data, and are listed only to platform
administrators (`super_admin`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, Session, mapped_column

from lumiant.audit.store import Base


class DemoRequestRow(Base):
    __tablename__ = "demo_request"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    received_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), index=True)
    name: Mapped[str] = mapped_column(sa.String(120))
    email: Mapped[str] = mapped_column(sa.String(254))
    company: Mapped[str] = mapped_column(sa.String(160))
    role: Mapped[str | None] = mapped_column(sa.String(120))
    systems: Mapped[str | None] = mapped_column(sa.String(200))
    message: Mapped[str | None] = mapped_column(sa.String(1000))


@dataclass(frozen=True)
class DemoRequest:
    name: str
    email: str
    company: str
    role: str | None = None
    systems: str | None = None
    message: str | None = None


class DemoRequestStore:
    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine

    def add(self, req: DemoRequest) -> int:
        with Session(self.engine) as session, session.begin():
            row = DemoRequestRow(received_at=datetime.now(UTC), **req.__dict__)
            session.add(row)
            session.flush()
            return int(row.id)

    def recent(self, limit: int = 100) -> list[dict[str, object]]:
        with Session(self.engine) as session:
            rows = session.scalars(sa.select(DemoRequestRow).order_by(DemoRequestRow.id.desc()).limit(limit)).all()
            return [
                {
                    "id": r.id,
                    "received_at": r.received_at.isoformat(),
                    "name": r.name,
                    "email": r.email,
                    "company": r.company,
                    "role": r.role,
                    "systems": r.systems,
                    "message": r.message,
                }
                for r in rows
            ]
