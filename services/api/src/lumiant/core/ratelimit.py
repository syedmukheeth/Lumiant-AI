"""In-process sliding-window rate limiter (per key). Protects chat, queries, exports and sign-in.

State lives in memory: with several API replicas each enforces its own limit. A shared store (Redis) is a
deployment decision for later; see docs/06-operations/PRODUCTION_READINESS.md.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

MAX_KEYS = 10_000


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
