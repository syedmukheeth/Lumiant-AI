"""Application wiring. One instance per app, stored on `app.state.container`."""

from __future__ import annotations

from dataclasses import dataclass

from lumiant.admin.service import AdminService
from lumiant.agent.service import AgentService
from lumiant.audit.store import AuditStore
from lumiant.auth.provider import DevAuthProvider
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.core.config import Settings
from lumiant.metrics.service import MetricsService
from lumiant.query.service import QueryService
from lumiant.reports.service import ReportService
from lumiant.tenancy.registry import TenantRegistry


@dataclass
class Container:
    settings: Settings
    tenants: TenantRegistry
    connectors: ConnectorRegistry
    audit: AuditStore
    query: QueryService
    metrics: MetricsService
    agent: AgentService
    reports: ReportService
    admin: AdminService
    dev_auth: DevAuthProvider | None

    def close(self) -> None:
        self.connectors.dispose_all()
        self.audit.dispose()
