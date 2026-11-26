"""Alert rules and signed webhooks (V3, docs/05-plan/PRODUCT_V3_PLAN.md §4).

A rule sends the insight findings at or above a severity to an HTTPS endpoint the customer controls (their ticketing,
chat or workflow tool). Each delivery is a JSON POST signed with HMAC-SHA256 over the exact body, so the receiver can
prove it came from Lumiant:

    X-Lumiant-Signature: sha256=<hex(hmac(secret, body))>
    X-Lumiant-Timestamp: <unix seconds, also inside the signed body>

- The signing secret is shown once; it is stored encrypted (same master key as saved connections) because signing
  needs it back. Without `LUMIANT_SECRET_KEY` rules cannot be created.
- Findings are computed for the person who sends (or created) the rule, with their warehouse scope and rights.
- Targets must be HTTPS in production and may not resolve to private, loopback or link-local addresses (no SSRF into
  the customer's or our own network). Development and tests may use http://localhost.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import sqlalchemy as sa
from cryptography.fernet import InvalidToken
from sqlalchemy.orm import Mapped, Session, mapped_column

from lumiant.audit.store import Base
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal, WarehouseScope
from lumiant.connectors.secret_store import KEY_ENV, _fernet
from lumiant.core.errors import AppError

SEVERITIES = ("info", "warning", "critical")
TIMEOUT_S = 5.0


class AlertRuleRow(Base):
    __tablename__ = "alert_rule"

    id: Mapped[str] = mapped_column(sa.String(24), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(sa.String(64), index=True)
    name: Mapped[str] = mapped_column(sa.String(80))
    url: Mapped[str] = mapped_column(sa.String(500))
    min_severity: Mapped[str] = mapped_column(sa.String(16))
    secret_cipher: Mapped[str] = mapped_column(sa.Text())
    created_by: Mapped[str] = mapped_column(sa.String(128))
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))
    last_sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(sa.String(120))
    active: Mapped[bool] = mapped_column(sa.Boolean())
    # Scheduled sending (0006): hours between deliveries, and the creator's rights at creation so a scheduled run
    # never sees more than the person who set the rule up could.
    every_hours: Mapped[int | None] = mapped_column(sa.Integer())
    permissions: Mapped[str] = mapped_column(sa.String(400), default="")
    scope_all: Mapped[bool] = mapped_column(sa.Boolean(), default=False)
    warehouses: Mapped[str] = mapped_column(sa.String(2000), default="")


def check_target(url: str, *, allow_local: bool) -> None:
    """Refuse targets that would let a rule reach private networks (SSRF) or send without TLS in production."""
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname:
        raise AppError("invalid_target", "Use a full https:// address.", 422)
    if allow_local:
        return
    if parsed.scheme != "https":
        raise AppError("invalid_target", "Webhooks must use https.", 422)
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise AppError("invalid_target", "That host name does not resolve.", 422) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise AppError("invalid_target", "Webhooks cannot target private or internal addresses.", 422)


def _public(row: AlertRuleRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "url": row.url,
        "min_severity": row.min_severity,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
        "last_sent_at": row.last_sent_at.isoformat() if row.last_sent_at else None,
        "last_status": row.last_status,
        "active": row.active,
        "every_hours": row.every_hours,
    }


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class AlertService:
    def __init__(self, engine: sa.Engine) -> None:
        self.engine = engine

    def create(
        self,
        principal: Principal,
        name: str,
        url: str,
        min_severity: str,
        *,
        allow_local: bool,
        every_hours: int | None = None,
    ) -> tuple[str, dict[str, Any]]:
        if min_severity not in SEVERITIES:
            raise AppError("invalid_request", "Severity must be info, warning or critical.", 422)
        check_target(url, allow_local=allow_local)
        f = _fernet()
        if f is None:
            raise AppError(
                "secret_store_unavailable", f"Alert rules need a master key in {KEY_ENV} on the server.", 409
            )
        secret = "whsec_" + secrets.token_urlsafe(32)
        row = AlertRuleRow(
            id=uuid.uuid4().hex[:12],
            tenant_id=principal.tenant_id,
            name=name,
            url=url,
            min_severity=min_severity,
            secret_cipher=f.encrypt(secret.encode("utf-8")).decode("ascii"),
            created_by=principal.user_id,
            created_at=datetime.now(UTC),
            last_sent_at=None,
            last_status=None,
            active=True,
            every_hours=every_hours,
            permissions=",".join(sorted(p.value for p in principal.permissions)),
            scope_all=principal.scope.all,
            warehouses=",".join(sorted(principal.scope.ids)),
        )
        with Session(self.engine) as session, session.begin():
            session.add(row)
            session.flush()
            record = _public(row)
        return secret, record

    def list_rules(self, tenant_id: str) -> list[dict[str, Any]]:
        with Session(self.engine) as session:
            rows = session.scalars(
                sa.select(AlertRuleRow)
                .where(AlertRuleRow.tenant_id == tenant_id)
                .order_by(AlertRuleRow.created_at.desc())
            ).all()
            return [_public(r) for r in rows]

    def delete(self, tenant_id: str, rule_id: str) -> bool:
        with Session(self.engine) as session, session.begin():
            row = session.get(AlertRuleRow, rule_id)
            if row is None or row.tenant_id != tenant_id:
                return False
            session.delete(row)
            return True

    def send(self, tenant_id: str, rule_id: str, feed: dict[str, Any], *, allow_local: bool) -> dict[str, Any]:
        """Deliver the feed's findings at or above the rule's severity. Records and returns the outcome."""
        with Session(self.engine) as session:
            row = session.get(AlertRuleRow, rule_id)
            if row is None or row.tenant_id != tenant_id:
                raise AppError("not_found", "No alert rule with that id.", 404)
            url, floor, cipher, name = row.url, row.min_severity, row.secret_cipher, row.name
        f = _fernet()
        try:
            secret = f.decrypt(cipher.encode("ascii")).decode("utf-8") if f else None
        except InvalidToken:
            secret = None
        if secret is None:
            raise AppError("secret_store_unavailable", "The rule's signing secret cannot be read on this server.", 409)
        check_target(url, allow_local=allow_local)
        rank = SEVERITIES.index(floor)
        findings = [i for i in feed.get("insights", []) if SEVERITIES.index(i.get("severity", "info")) >= rank]
        ts = int(time.time())
        payload = {
            "rule": {"id": rule_id, "name": name, "min_severity": floor},
            "tenant_id": tenant_id,
            "timestamp": ts,
            "data_as_of": feed.get("data_as_of"),
            "complete": feed.get("complete"),
            "warnings": feed.get("warnings", []),
            "findings": [
                {k: i.get(k) for k in ("id", "severity", "category", "title", "detail", "metrics")} for i in findings
            ],
        }
        body = json.dumps(payload, default=str, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 (scheme checked above: http(s) only)
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Lumiant-Webhooks/1",
                "X-Lumiant-Signature": sign(secret, body),
                "X-Lumiant-Timestamp": str(ts),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as resp:  # noqa: S310
                status = f"delivered ({resp.status})"
                ok = 200 <= resp.status < 300
        except urllib.error.HTTPError as exc:
            status, ok = f"refused by receiver ({exc.code})", False
        except (urllib.error.URLError, TimeoutError, OSError):
            status, ok = "receiver unreachable", False
        with Session(self.engine) as session, session.begin():
            row = session.get(AlertRuleRow, rule_id)
            if row is not None:
                row.last_sent_at = datetime.now(UTC)
                row.last_status = status
        return {"ok": ok, "status": status, "findings": len(findings)}

    def due(self, now: datetime | None = None) -> list[tuple[str, Principal]]:
        """Scheduled rules whose interval has passed, each with the principal it runs as (its creator's snapshot)."""
        now = now or datetime.now(UTC)
        out: list[tuple[str, Principal]] = []
        with Session(self.engine) as session:
            rows = session.scalars(
                sa.select(AlertRuleRow).where(AlertRuleRow.active.is_(True), AlertRuleRow.every_hours.is_not(None))
            ).all()
            for r in rows:
                last = r.last_sent_at
                if last is not None and last.tzinfo is None:
                    last = last.replace(tzinfo=UTC)
                if last is not None and (now - last).total_seconds() < (r.every_hours or 0) * 3600:
                    continue
                principal = Principal(
                    user_id=f"alert:{r.id}",
                    display_name=r.name,
                    tenant_id=r.tenant_id,
                    roles=("alert_rule",),
                    permissions=frozenset(Permission(p) for p in r.permissions.split(",") if p),
                    scope=WarehouseScope(r.scope_all, frozenset(w for w in r.warehouses.split(",") if w)),
                )
                out.append((r.id, principal))
        return out
