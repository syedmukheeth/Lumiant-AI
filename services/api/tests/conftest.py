"""Shared fixtures: small deterministic synthetic warehouses generated once per test session."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from lumiant.audit.store import AuditStore, run_migrations
from lumiant.auth.principal import Principal, principal_for_dev_user
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.core.config import BASE_DIR
from lumiant.query.service import QueryService
from lumiant.synthetic.cli import generate_tenant
from lumiant.tenancy.registry import TenantRegistry

# Tests sign in many times from one address; rate-limit behaviour has its own tests with explicit settings.
os.environ.setdefault("LUMIANT_RATE_LIMIT_LOGIN_PER_MIN", "100000")
os.environ.setdefault("LUMIANT_RATE_LIMIT_EXPORT_PER_MIN", "100000")
os.environ.setdefault("LUMIANT_RATE_LIMIT_CHAT_PER_MIN", "100000")

TENANT_DIR = BASE_DIR / "config" / "tenants"
AS_OF = date(2026, 10, 1)
TEST_ITEMS = {"demo-alpha": 90, "demo-beta": 60}
TEST_MONTHS = 12


@pytest.fixture(scope="session")
def registry() -> TenantRegistry:
    return TenantRegistry.load(TENANT_DIR)


@pytest.fixture(scope="session")
def data_dir(tmp_path_factory: pytest.TempPathFactory, registry: TenantRegistry) -> Path:
    root = tmp_path_factory.mktemp("lumiant-data")
    for tenant_id, n_items in TEST_ITEMS.items():
        generate_tenant(tenant_id, registry=registry, data_dir=root, as_of=AS_OF, n_items=n_items, months=TEST_MONTHS)
    return root


@pytest.fixture(scope="session")
def alpha_db(data_dir: Path) -> Path:
    return data_dir / "data" / "synthetic" / "demo-alpha.duckdb"


@pytest.fixture(scope="session")
def beta_db(data_dir: Path) -> Path:
    return data_dir / "data" / "synthetic" / "demo-beta.duckdb"


@pytest.fixture(scope="session")
def audit_store(tmp_path_factory: pytest.TempPathFactory) -> AuditStore:
    url = f"sqlite:///{(tmp_path_factory.mktemp('appdb') / 'app.db').as_posix()}"
    run_migrations(url)
    return AuditStore(url)


@pytest.fixture(scope="session")
def query_service(registry: TenantRegistry, data_dir: Path, audit_store: AuditStore) -> QueryService:
    return QueryService(registry, ConnectorRegistry(registry, data_dir), audit_store)


@pytest.fixture(scope="session")
def principals(registry: TenantRegistry) -> dict[str, Principal]:
    result: dict[str, Principal] = {}
    for tenant in registry:
        for user in tenant.dev_users:
            result[user.username] = principal_for_dev_user(tenant, user)
    return result
