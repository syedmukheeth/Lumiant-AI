"""V1: a tested connection can be saved encrypted from Admin > Data source and used by a `secret_ref: store` tenant;
without a master key nothing is stored; the URL never comes back out."""

from __future__ import annotations

from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from lumiant.audit.store import AuditStore
from lumiant.auth.principal import principal_for_dev_user
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.connectors.secret_store import KEY_ENV, SourceSecretStore, new_key
from lumiant.core.config import Settings
from lumiant.core.errors import AppError
from lumiant.main import create_app
from lumiant.metrics.service import MetricsService
from lumiant.query.service import QueryService
from lumiant.synthetic.copy import copy_duckdb
from lumiant.tenancy.models import ConnectionConfig
from lumiant.tenancy.registry import TenantRegistry
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


@pytest.fixture
def sqlite_url(alpha_db: Path, tmp_path: Path) -> str:
    target = tmp_path / "alpha.sqlite"
    copy_duckdb(alpha_db, f"sqlite:///{target.as_posix()}")
    return f"sqlite:///{target.as_posix()}"


@pytest.fixture
def master_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KEY_ENV, new_key())


def test_saving_needs_a_master_key(audit_store: AuditStore, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(KEY_ENV, raising=False)
    store = SourceSecretStore(audit_store.engine)
    with pytest.raises(AppError) as exc:
        store.save("demo-alpha", "sqlite:///x.db", "sqlite", "tester")
    assert exc.value.code == "secret_store_unavailable"


def test_saved_url_is_encrypted_and_used_by_a_store_tenant(
    master_key: None, audit_store: AuditStore, registry: TenantRegistry, data_dir: Path, sqlite_url: str
) -> None:
    store = SourceSecretStore(audit_store.engine)
    store.save("demo-alpha", sqlite_url, "sqlite", "tester")
    with audit_store.engine.connect() as conn:
        raw = conn.execute(sa.text("SELECT ciphertext FROM source_secret WHERE tenant_id = 'demo-alpha'")).scalar()
    assert raw
    assert "sqlite" not in raw
    assert store.url("demo-alpha") == sqlite_url

    alpha = registry.get("demo-alpha")
    cfg = alpha.model_copy(update={"connection": ConnectionConfig(type="sql", secret_ref="store")})
    tenants = TenantRegistry({"demo-alpha": cfg})
    connectors = ConnectorRegistry(tenants, data_dir, store)
    try:
        svc = QueryService(tenants, connectors, audit_store)
        admin = principal_for_dev_user(cfg, next(u for u in cfg.dev_users if u.username == "alpha.admin"))
        _, items = MetricsService(svc).run("items_in_stock", admin)
        assert int(items.rows[0]["items"]) > 0
    finally:
        connectors.dispose_all()
    store.delete("demo-alpha")


def test_a_wrong_key_fails_closed(
    master_key: None, audit_store: AuditStore, monkeypatch: pytest.MonkeyPatch, sqlite_url: str
) -> None:
    store = SourceSecretStore(audit_store.engine)
    store.save("demo-beta", sqlite_url, "sqlite", "tester")
    monkeypatch.setenv(KEY_ENV, new_key())
    assert store.url("demo-beta") is None
    store.delete("demo-beta")


def test_save_endpoint_is_admin_only_and_never_returns_the_url(
    master_key: None, data_dir: Path, tmp_path: Path, sqlite_url: str
) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="store-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as client:
        client.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF)
        saved = client.post("/api/admin/source/save", json={"url": sqlite_url}, headers=CSRF)
        assert saved.status_code == 200
        assert saved.json()["saved"] is True
        assert "alpha.sqlite" not in saved.text
        status = client.get("/api/admin/source/saved").json()
        assert status["saved"] is True
        assert status["in_use"] is False  # demo-alpha's config still points at its DuckDB file
        assert "alpha.sqlite" not in str(status)
        client.cookies.clear()
        client.post("/api/auth/dev-login", json={"username": "alpha.analyst"}, headers=CSRF)
        assert client.post("/api/admin/source/save", json={"url": sqlite_url}, headers=CSRF).status_code == 403
