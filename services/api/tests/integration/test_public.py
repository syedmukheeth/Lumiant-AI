"""Public landing-page endpoints: demo requests (Product v2, D3)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lumiant.core.config import Settings
from lumiant.main import create_app
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}
GOOD: dict[str, Any] = {
    "name": "Dana Planner",
    "email": "Dana@Example.com",
    "company": "Example Industrial",
    "systems": "SAP S/4HANA",
    "message": "Interested in dormant stock",
    "consent": True,
}


@pytest.fixture(scope="module")
def client(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("public-appdb") / "app.db"),
        log_level="WARNING",
        rate_limit_enabled=False,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client: TestClient, username: str) -> None:
    client.cookies.clear()
    assert client.post("/api/auth/dev-login", json={"username": username}, headers=CSRF).status_code == 200


def test_a_visitor_can_request_a_demo_without_signing_in(client: TestClient) -> None:
    client.cookies.clear()
    r = client.post("/api/public/demo-requests", json=GOOD, headers=CSRF)
    assert r.status_code == 202
    login(client, "alpha.admin")
    rows = client.get("/api/admin/demo-requests").json()["requests"]
    assert rows[0]["email"] == "dana@example.com"
    assert rows[0]["company"] == "Example Industrial"


@pytest.mark.security
def test_demo_requests_need_csrf_consent_and_a_valid_email(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/public/demo-requests", json=GOOD).status_code == 403
    assert client.post("/api/public/demo-requests", json={**GOOD, "consent": False}, headers=CSRF).status_code == 422
    for bad in ("not-an-email", "a@b", "x <x@y.com>", "a@b.c"):
        r = client.post("/api/public/demo-requests", json={**GOOD, "email": bad}, headers=CSRF)
        assert r.status_code == 422, bad
    assert client.post("/api/public/demo-requests", json={**GOOD, "extra": 1}, headers=CSRF).status_code == 422
    too_long = {**GOOD, "message": "x" * 1001}
    assert client.post("/api/public/demo-requests", json=too_long, headers=CSRF).status_code == 422


def test_honeypot_submissions_are_accepted_but_not_stored(client: TestClient) -> None:
    client.cookies.clear()
    r = client.post(
        "/api/public/demo-requests", json={**GOOD, "company": "Bot Co", "website": "http://spam"}, headers=CSRF
    )
    assert r.status_code == 202
    login(client, "alpha.admin")
    assert all(row["company"] != "Bot Co" for row in client.get("/api/admin/demo-requests").json()["requests"])


def test_control_characters_are_stripped(client: TestClient) -> None:
    client.cookies.clear()
    body = {**GOOD, "company": "Ctrl\x07 Co\x00", "email": "ctrl@example.com"}
    assert client.post("/api/public/demo-requests", json=body, headers=CSRF).status_code == 202
    login(client, "alpha.admin")
    row = next(r for r in client.get("/api/admin/demo-requests").json()["requests"] if r["email"] == "ctrl@example.com")
    assert row["company"] == "Ctrl Co"


@pytest.mark.security
def test_only_platform_admins_can_read_demo_requests(client: TestClient) -> None:
    client.cookies.clear()
    assert client.get("/api/admin/demo-requests").status_code == 401
    login(client, "alpha.analyst")
    assert client.get("/api/admin/demo-requests").status_code == 403
    login(client, "alpha.north_manager")  # tenant/department admin, not a platform admin
    assert client.get("/api/admin/demo-requests").status_code == 403
