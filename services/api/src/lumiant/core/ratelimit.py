"""Sliding-window rate limiting (per key). Protects chat, queries, exports and sign-in.

Default: `RateLimiter`, in process memory, so each API replica enforces its own limit. Optional: when
LUMIANT_RATE_LIMIT_REDIS_URL is set, `RedisRateLimiter` shares the windows between replicas (ISSUES #18).
Both implement `Limiter`. If Redis is unreachable the Redis limiter degrades to the in-process one rather than
failing open or taking the API down; the degradation is logged (never the URL, which may hold a password).
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lumiant.core.config import Settings

log = logging.getLogger("lumiant.ratelimit")

MAX_KEYS = 10_000


class Limiter(Protocol):
    def hit(self, key: str, limit: int, window_s: float) -> tuple[bool, int]:
        """Record an attempt. Returns (allowed, retry_after_seconds)."""
        ...

    def close(self) -> None: ...


class RateLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_s: float) -> tuple[bool, int]:
        """Record an attempt. Returns (allowed, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > MAX_KEYS:
                self._prune(now, window_s)
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] >= window_s:
                q.popleft()
            if len(q) >= limit:
                return False, max(1, int(window_s - (now - q[0])) + 1)
            q.append(now)
            return True, 0

    def _prune(self, now: float, window_s: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or now - q[-1] >= window_s]:
            del self._hits[k]

    def close(self) -> None:
        return None


# Atomic sliding window on a sorted set. Uses the Redis server clock so replicas with skewed clocks agree.
# Returns {allowed (1/0), retry_after_seconds}.
_SLIDING_WINDOW_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000
local window = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) >= limit then
  local oldest = tonumber(redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')[2])
  local retry = math.floor(window - (now - oldest)) + 1
  if retry < 1 then retry = 1 end
  return {0, retry}
end
redis.call('ZADD', KEYS[1], now, ARGV[3])
redis.call('PEXPIRE', KEYS[1], math.ceil(window * 1000))
return {1, 0}
"""


class RedisRateLimiter:
    """Shared sliding window. `client` is injectable for tests; otherwise built from `url` (optional extra: redis)."""

    def __init__(
        self,
        url: str | None = None,
        *,
        client: Any = None,
        prefix: str = "lumiant:rl:",
        fallback: Limiter | None = None,
    ) -> None:
        if client is None:
            try:
                import redis
            except ImportError as exc:  # pragma: no cover - depends on the optional extra
                raise RuntimeError(
                    "LUMIANT_RATE_LIMIT_REDIS_URL is set but the 'redis' extra is not installed"
                ) from exc
            if not url:
                raise ValueError("a Redis URL or client is required")
            client = redis.Redis.from_url(url, socket_connect_timeout=1.0, socket_timeout=1.0)
        self._client = client
        self._script = client.register_script(_SLIDING_WINDOW_LUA)
        self._prefix = prefix
        self._fallback = fallback or RateLimiter()
        self._degraded = False

    def hit(self, key: str, limit: int, window_s: float) -> tuple[bool, int]:
        try:
            allowed, retry = self._script(keys=[self._prefix + key], args=[window_s, limit, uuid.uuid4().hex])
        except Exception as exc:  # any transport/script error: stay protected locally, never fail open
            if not self._degraded:
                log.error("rate_limit_redis_unavailable", extra={"error_type": type(exc).__name__})
                self._degraded = True
            return self._fallback.hit(key, limit, window_s)
        if self._degraded:
            log.warning("rate_limit_redis_recovered")
            self._degraded = False
        return bool(int(allowed)), int(retry)

    def close(self) -> None:
        with contextlib.suppress(Exception):  # shutting down; nothing useful to do with a close error
            self._client.close()


def build_limiter(settings: Settings) -> Limiter:
    url = settings.rate_limit_redis_url.get_secret_value() if settings.rate_limit_redis_url else None
    if settings.rate_limit_enabled and url:
        return RedisRateLimiter(url)
    return RateLimiter()
