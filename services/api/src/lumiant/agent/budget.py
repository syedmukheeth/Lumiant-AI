"""Daily AI allowance per organisation (DEC-037).

Every call to an external model (choosing tools, each review round, embeddings for knowledge search) spends one unit
from a rolling 24-hour window per tenant. When it is spent, the Analyst answers with built-in question matching and
says so; nothing fails. The window reuses the rate limiter, so it is shared between API instances only when
LUMIANT_RATE_LIMIT_REDIS_URL is set; otherwise each instance keeps its own count (ISSUES #63).
"""

from __future__ import annotations

from lumiant.core.ratelimit import Limiter, RateLimiter

WINDOW_S = 86_400.0
EXHAUSTED_NOTICE = "Today's AI allowance for this organisation is used up; using built-in question matching."


class AiBudget:
    def __init__(self, limiter: Limiter | None, daily_calls: int) -> None:
        self._limiter = limiter or RateLimiter()
        self.daily_calls = daily_calls

    def spend(self, tenant_id: str) -> bool:
        """Take one model call from the tenant's allowance. False when none is left (or the allowance is zero)."""
        if self.daily_calls <= 0:
            return False
        allowed, _retry = self._limiter.hit(f"ai-budget:{tenant_id}", self.daily_calls, WINDOW_S)
        return allowed
