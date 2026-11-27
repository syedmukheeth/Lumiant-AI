"""Send scheduled alert rules that are due. Run it from cron or a Kubernetes CronJob, for example every 15 minutes:

    uv run lumiant-alerts send-due

Each due rule computes the insight feed with its creator's rights and warehouse scope (snapshot taken when the rule
was created) and delivers the matching findings to its webhook, signed. Needs LUMIANT_SECRET_KEY like the API.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from lumiant.alerts.service import AlertService
from lumiant.audit.store import AuditStore, run_migrations
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.connectors.secret_store import SourceSecretStore
from lumiant.core.config import Settings, get_settings
from lumiant.core.errors import AppError
from lumiant.insights.engine import InsightService
from lumiant.query.service import QueryService
from lumiant.tenancy.registry import TenantRegistry


def send_due(settings: Settings | None = None) -> list[dict[str, Any]]:
    cfg = settings or get_settings()
    run_migrations(cfg.app_db_url)
    audit = AuditStore(cfg.app_db_url)
    tenants = TenantRegistry.load(cfg.tenant_config_dir)
    connectors = ConnectorRegistry(tenants, cfg.data_dir, SourceSecretStore(audit.engine))
    query = QueryService(tenants, connectors, audit)
    alerts = AlertService(audit.engine)
    results: list[dict[str, Any]] = []
    try:
        for rule_id, principal in alerts.due():
            if not tenants.has(principal.tenant_id):
                continue
            try:
                feed = InsightService(query).feed(principal, fresh=True)
                outcome = alerts.send(principal.tenant_id, rule_id, feed, allow_local=not cfg.is_production)
            except AppError as exc:
                outcome = {"ok": False, "status": exc.code}
            query.record(principal, "alert:scheduled_send", None, "allow", "ok" if outcome.get("ok") else "error")
            results.append({"rule": rule_id, **outcome})
    finally:
        connectors.dispose_all()
        audit.dispose()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lumiant-alerts", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("send-due", help="send every scheduled alert rule whose interval has passed")
    parser.parse_args(argv)
    results = send_due()
    print(json.dumps({"sent": results}, indent=2))
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
