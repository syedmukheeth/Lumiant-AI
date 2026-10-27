# ADR-0007: Nonce-based CSP with per-request rendering; optional Redis rate-limit store

- **Status:** Accepted
- **Date:** 2026-10-27
- **Session:** cloud-verify
- **Related:** ISSUES #9, #18, #19; `../../06-operations/PRODUCTION_READINESS.md`

## Context
The first CSP allowed `'unsafe-inline'` scripts because Next.js bootstraps with inline scripts. The rate limiter held its windows in process memory, so N replicas allowed N times the limit.

## Decision
1. **CSP**: `src/proxy.ts` generates a fresh nonce per request and sets `script-src 'self' 'nonce-…'` (no `'unsafe-inline'`, no `'strict-dynamic'`) on the request (so Next.js stamps its inline scripts) and the response. The inline theme script moved to the same-origin `public/theme-init.js`, loaded with `next/script`. The root layout calls `connection()` so every page is rendered per request, and `cacheComponents` / `partialPrefetching` were turned off: a prerendered shell cannot carry a per-request nonce (verified: the static shell's inline scripts had no nonce). `style-src` keeps `'unsafe-inline'` because React/Recharts emit style attributes, which a nonce cannot cover.
2. **Rate limit**: `Limiter` protocol with two implementations. Default `RateLimiter` (in process). When `LUMIANT_RATE_LIMIT_REDIS_URL` is set (secret; needs the `redis` extra) `RedisRateLimiter` uses an atomic Lua sliding window on a sorted set with the Redis server clock. If Redis errors it degrades to an in-process limiter (logged once, without the URL) instead of failing open or failing requests.

## Consequences
Inline-script XSS is blocked by the browser. Pages are no longer prerendered (they were thin client-driven shells; no measurable loss, no server data access). Limits hold across replicas when Redis is configured. During a Redis outage limits are per replica again.

## Alternatives considered
Hash-based CSP — Next.js inline script contents change per render. Keep prerendering with a nonce — not possible. Fail open or closed on Redis outage — open removes protection, closed makes Redis a hard availability dependency of every request.

## Revisit when
Next.js supports nonces on partially prerendered shells; a customer requires `style-src` without `'unsafe-inline'`; the API gets another shared state store (then reuse it).
