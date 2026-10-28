"""App factory. Run with: uv run uvicorn --factory lumiant.main:create_app --port 8000"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lumiant import __version__
from lumiant.admin.service import AdminService
from lumiant.agent.service import AgentService
from lumiant.api import admin, agent, analyses, auth, health, insights, inventory, meta, metrics, query, reports
from lumiant.audit.store import AuditStore, run_migrations
from lumiant.auth.oidc import OidcAuthProvider
from lumiant.auth.provider import DevAuthProvider
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.container import Container
from lumiant.core.config import AuthMode, Settings, get_settings
from lumiant.core.errors import install_error_handlers
from lumiant.core.logging import configure_logging
from lumiant.core.ratelimit import build_limiter
from lumiant.core.request_context import RequestContextMiddleware
from lumiant.insights.engine import InsightService
from lumiant.metrics.service import MetricsService
from lumiant.query.service import QueryService
from lumiant.reports.service import ReportService
from lumiant.tenancy.registry import TenantRegistry


def build_container(settings: Settings) -> Container:
    tenants = TenantRegistry.load(settings.tenant_config_dir, settings.private_tenants_dir)
    extracts = [t.id for t in tenants if t.customer_extract]
    if extracts and settings.is_production:  # defence in depth: Settings already refuses the private directory
        raise RuntimeError(f"customer extract tenants cannot run in production: {', '.join(extracts)} (ADR-0008)")
    oidc = OidcAuthProvider(tenants) if settings.auth_mode is AuthMode.OIDC else None  # fails fast if unconfigured
    if settings.auto_migrate:
        run_migrations(settings.app_db_url)
    audit = AuditStore(settings.app_db_url)
    connectors = ConnectorRegistry(tenants, settings.data_dir)
    query_service = QueryService(tenants, connectors, audit)
    reports = ReportService(query_service)
    return Container(
        settings=settings,
        tenants=tenants,
        connectors=connectors,
        audit=audit,
        query=query_service,
        metrics=MetricsService(query_service),
        agent=AgentService(query_service, settings),
        reports=reports,
        admin=AdminService(query_service, reports),
        insights=InsightService(query_service),
        dev_auth=DevAuthProvider(settings, tenants) if settings.dev_auth_enabled else None,
        oidc=oidc,
        limiter=build_limiter(settings),
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = build_container(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        container.close()

    docs = not settings.is_production
    app = FastAPI(
        title="Lumiant Inventory Intelligence API",
        version=__version__,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
        lifespan=lifespan,
    )
    app.state.container = container
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    for module in (health, auth, meta, metrics, inventory, analyses, agent, insights, reports, admin, query):
        app.include_router(module.router)
    return app
