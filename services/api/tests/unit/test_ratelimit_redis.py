"""Shared (Redis) rate limiter: real-server tests need LUMIANT_TEST_REDIS_URL; fallback tests run everywhere."""

from __future__ import annotations

import os
import time
import uuid
from collections.abc import Iterator
from typing import Any

import pytest

from lumiant.core.config import Settings
from lumiant.core.ratelimit import RateLimiter, RedisRateLimiter, build_limiter

REDIS_URL = os.environ.get("LUMIANT_TEST_REDIS_URL")
needs_redis = pytest.mark.skipif(not REDIS_URL, reason="needs LUMIANT_TEST_REDIS_URL")


class BrokenClient:
    def register_script(self, _: str) -> Any:
        def call(**_kw: Any) -> Any:
            raise ConnectionError("redis://user:secret@host is down")

        return call

    def close(self) -> None:
        raise RuntimeError("ignored on shutdown")


def test_default_is_in_process_limiter() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.rate_limit_redis_url is None
    assert type(build_limiter(settings)) is RateLimiter


def test_redis_url_is_a_secret() -> None:
    settings = Settings(_env_file=None, rate_limit_redis_url="redis://:pw@cache:6379/0")  # type: ignore[call-arg]
    assert "pw" not in repr(settings)


def test_outage_degrades_to_local_limits_and_never_fails_open(caplog: pytest.LogCaptureFixture) -> None:
    rl = RedisRateLimiter(client=BrokenClient())
    assert [rl.hit("k", 2, 60)[0] for _ in range(3)] == [True, True, False]
    errors = [r for r in caplog.records if r.message == "rate_limit_redis_unavailable"]
    assert len(errors) == 1  # logged once, not per request
    assert "secret" not in caplog.text
    rl.close()  # swallows client errors


@pytest.fixture
def prefix() -> str:
    return f"lumiant:test:{uuid.uuid4().hex}:"


@pytest.fixture
def clients() -> Iterator[list[RedisRateLimiter]]:
    made: list[RedisRateLimiter] = []
    yield made
    for m in made:
        m.close()


@needs_redis
def test_limit_is_shared_between_instances(prefix: str, clients: list[RedisRateLimiter]) -> None:
    a = RedisRateLimiter(REDIS_URL, prefix=prefix)
    b = RedisRateLimiter(REDIS_URL, prefix=prefix)
    clients += [a, b]
    assert [a.hit("u", 3, 60)[0], b.hit("u", 3, 60)[0], a.hit("u", 3, 60)[0]] == [True] * 3
    allowed, retry = b.hit("u", 3, 60)  # a different "replica" sees the same window
    assert allowed is False
    assert 1 <= retry <= 61
    assert a.hit("someone-else", 3, 60)[0] is True  # keys are independent


@needs_redis
def test_window_slides_and_recovers(prefix: str, clients: list[RedisRateLimiter]) -> None:
    rl = RedisRateLimiter(REDIS_URL, prefix=prefix)
    clients.append(rl)
    assert [rl.hit("k", 2, 1)[0], rl.hit("k", 2, 1)[0]] == [True, True]
    allowed, retry = rl.hit("k", 2, 1)
    assert (allowed, retry) == (False, 1)
    time.sleep(1.2)
    assert rl.hit("k", 2, 1)[0] is True


@needs_redis
def test_keys_expire(prefix: str, clients: list[RedisRateLimiter]) -> None:
    import redis

    rl = RedisRateLimiter(REDIS_URL, prefix=prefix)
    clients.append(rl)
    rl.hit("k", 5, 30)
    r = redis.Redis.from_url(REDIS_URL)
    ttl = r.pttl(prefix + "k")
    assert 0 < ttl <= 30_000
    r.close()


@needs_redis
def test_build_limiter_uses_redis_when_configured() -> None:
    settings = Settings(_env_file=None, rate_limit_redis_url=REDIS_URL)  # type: ignore[call-arg]
    limiter = build_limiter(settings)
    try:
        assert isinstance(limiter, RedisRateLimiter)
    finally:
        limiter.close()
