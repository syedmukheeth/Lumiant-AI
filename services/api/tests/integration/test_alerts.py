"""V3 alert rules: deliveries are signed and verifiable, filtered by severity, and private targets are refused."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lumiant.alerts.service import check_target, sign
from lumiant.connectors.secret_store import KEY_ENV, new_key
from lumiant.core.config import Settings
from lumiant.core.errors import AppError
from lumiant.main import create_app
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


class Receiver:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, str], bytes]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = self.rfile.read(int(self.headers["Content-Length"]))
                outer.calls.append(({k.lower(): v for k, v in self.headers.items()}, body))
                self.send_response(204)
                self.end_headers()

            def log_message(self, *args: Any) -> None:
                return

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/hook"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def receiver() -> Iterator[Receiver]:
    r = Receiver()
    yield r
    r.server.shutdown()


@pytest.fixture
def client(data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv(KEY_ENV, new_key())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="alerts-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF)
        yield c


def test_a_delivery_is_signed_and_filtered(client: TestClient, receiver: Receiver) -> None:
    created = client.post(
        "/api/admin/alerts", json={"name": "Ops", "url": receiver.url, "min_severity": "critical"}, headers=CSRF
    ).json()
    secret, rule = created["secret"], created["record"]
    assert secret.startswith("whsec_")
    assert secret not in str(client.get("/api/admin/alerts").json())
    sent = client.post(f"/api/admin/alerts/{rule['id']}/send", headers=CSRF).json()
    assert sent["ok"] is True
    headers, body = receiver.calls[-1]
    assert headers["x-lumiant-signature"] == sign(secret, body)
    payload = json.loads(body)
    assert payload["tenant_id"] == "demo-alpha"
    assert all(f["severity"] == "critical" for f in payload["findings"])
    assert len(payload["findings"]) == sent["findings"]
    listed = client.get("/api/admin/alerts").json()["rules"]
    assert listed[0]["last_status"].startswith("delivered")


def test_an_unreachable_receiver_is_reported(client: TestClient) -> None:
    rule = client.post(
        "/api/admin/alerts", json={"name": "Gone", "url": "http://127.0.0.1:9/nothing"}, headers=CSRF
    ).json()["record"]
    sent = client.post(f"/api/admin/alerts/{rule['id']}/send", headers=CSRF).json()
    assert sent["ok"] is False
    assert sent["status"] == "receiver unreachable"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com/hook",
        "https://127.0.0.1/hook",
        "https://10.1.2.3/hook",
        "https://169.254.169.254/x",
        "ftp://x/y",
    ],
)
def test_production_refuses_unsafe_targets(url: str) -> None:
    with pytest.raises(AppError) as exc:
        check_target(url, allow_local=False)
    assert exc.value.code == "invalid_target"


def test_rules_are_admin_only(client: TestClient) -> None:
    client.cookies.clear()
    client.post("/api/auth/dev-login", json={"username": "alpha.analyst"}, headers=CSRF)
    assert client.get("/api/admin/alerts").status_code == 403
