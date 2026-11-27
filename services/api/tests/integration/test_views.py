"""Saved views: private to their owner, only the page's known query keys are kept."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lumiant.core.config import Settings
from lumiant.main import create_app
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


def test_saved_views_are_private_and_cleaned(data_dir: Path, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="views-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF)
        v = c.post(
            "/api/views",
            json={"page": "inventory", "name": "Pumps", "query": "?warehouse=1100&evil=1&sort=item_code"},
            headers=CSRF,
        ).json()
        assert v["query"] == "warehouse=1100&sort=item_code"
        assert [x["name"] for x in c.get("/api/views", params={"page": "inventory"}).json()["views"]] == ["Pumps"]
        c.cookies.clear()
        c.post("/api/auth/dev-login", json={"username": "alpha.analyst"}, headers=CSRF)
        assert c.get("/api/views", params={"page": "inventory"}).json()["views"] == []
        assert c.delete(f"/api/views/{v['id']}", headers=CSRF).status_code == 404
