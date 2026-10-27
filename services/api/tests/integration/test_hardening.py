"""Hardening: rate limiting and the error contract for 429."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lumiant.core.config import Settings
from lumiant.core.ratelimit import RateLimiter
from lumiant.main import create_app
from tests.helpers import app_db_url

CSRF = {"X-Requested-With": "lumiant"}


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_sliding_window_limits_and_recovers() -> None:
    clock = FakeClock()
    rl = RateLimiter(clock)
    assert [rl.hit("k", 3, 60)[0] for _ in range(3)] == [True, True, True]
    allowed, retry = rl.hit("k", 3, 60)
    assert (allowed, 1 <= retry <= 61) == (False, True)
    assert rl.hit("other", 3, 60)[0] is True  # keys are independent
    clock.now += 61
    assert rl.hit("k", 3, 60)[0] is True


def test_window_is_sliding_not_fixed() -> None:
    clock = FakeClock()
    rl = RateLimiter(clock)
    rl.hit("k", 2, 60)
    clock.now += 30
    rl.hit("k", 2, 60)
    assert rl.hit("k", 2, 60)[0] is False
    clock.now += 31  # first hit leaves the window, second is still inside
    assert rl.hit("k", 2, 60)[0] is True
    assert rl.hit("k", 2, 60)[0] is False


@pytest.fixture
def client(data_dir: Path, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="limit-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app.db"),
        log_level="WARNING",
        rate_limit_chat_per_min=3,
        rate_limit_export_per_min=2,
        rate_limit_login_per_min=4,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client: TestClient, user: str) -> None:
    assert client.post("/api/auth/dev-login", json={"username": user}, headers=CSRF).status_code == 200


@pytest.mark.security
def test_chat_is_rate_limited_per_user(client: TestClient) -> None:
    login(client, "alpha.admin")
    codes = [
        client.post("/api/agent/chat", json={"message": "Which lots are nearing expiry?"}, headers=CSRF).status_code
        for _ in range(4)
    ]
    assert codes == [200, 200, 200, 429]
    blocked = client.post("/api/agent/chat", json={"message": "Which lots are nearing expiry?"}, headers=CSRF)
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1
    client.cookies.clear()
    login(client, "alpha.north_manager")  # a different user has their own allowance
    assert (
        client.post("/api/agent/chat", json={"message": "Which lots are nearing expiry?"}, headers=CSRF).status_code
        == 200
    )


@pytest.mark.security
def test_exports_are_rate_limited(client: TestClient) -> None:
    login(client, "alpha.admin")
    codes = [client.get("/api/reports/below_reorder/export").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


@pytest.mark.security
def test_sign_in_attempts_are_rate_limited_by_address(client: TestClient) -> None:
    codes = [
        client.post("/api/auth/dev-login", json={"username": "mallory"}, headers=CSRF).status_code for _ in range(5)
    ]
    assert codes[:4] == [401, 401, 401, 401]
    assert codes[4] == 429


def test_limits_can_be_disabled(data_dir: Path, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="limit-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path / "app2.db"),
        log_level="WARNING",
        rate_limit_enabled=False,
        rate_limit_login_per_min=1,
    )
    with TestClient(create_app(settings)) as c:
        assert all(
            c.post("/api/auth/dev-login", json={"username": "mallory"}, headers=CSRF).status_code == 401
            for _ in range(3)
        )
