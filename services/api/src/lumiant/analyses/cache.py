"""Short-lived result cache for analyses that several screens and the insight feed ask for at the same moment.

One Overview load used to run below-reorder five times and the same "missing valuation price" count five times
(TEST_RUNS S10-25). Results are shared only between callers with the same tenant, warehouse scope and permissions,
and only for the same data timestamp, so a cached figure is exactly the figure the caller would have computed.

- Never crosses scope: the key holds the tenant, the scope ids (or "all") and the permission set.
- New data is never hidden: the key holds the source's data timestamp (`tenant_meta`), and entries live 60 s.
- Errors are never cached: a failed run raises and stores nothing.
- `fresh_results()` bypasses the cache (the insight feed's Refresh); concurrent callers for one key wait for the
  first run instead of repeating it.
- Hits are written to the audit log with reason "cache".

Per process, like the insight feed's cache (ISSUES #37); a shared store comes with the worker in V1.
"""

from __future__ import annotations

import copy
import threading
import time
import weakref
from collections.abc import Callable, Hashable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from lumiant.auth.principal import Principal
from lumiant.query.service import QueryService

TTL_S = 60.0
MAX_ENTRIES = 512

_bypass: ContextVar[bool] = ContextVar("lumiant_results_bypass", default=False)


@contextmanager
def fresh_results() -> Iterator[None]:
    """Run the block without reading cached results (new results are still stored for the next caller)."""
    token = _bypass.set(True)
    try:
        yield
    finally:
        _bypass.reset(token)


class _Store:
    def __init__(self) -> None:
        self.entries: dict[Hashable, tuple[float, object]] = {}
        self.locks: dict[Hashable, threading.Lock] = {}
        self.guard = threading.Lock()

    def lock_for(self, key: Hashable) -> threading.Lock:
        with self.guard:
            return self.locks.setdefault(key, threading.Lock())

    def get(self, key: Hashable) -> object | None:
        with self.guard:
            hit = self.entries.get(key)
            if hit is None:
                return None
            if time.monotonic() - hit[0] >= TTL_S:
                del self.entries[key]
                self.locks.pop(key, None)
                return None
            return hit[1]

    def put(self, key: Hashable, value: object) -> None:
        with self.guard:
            now = time.monotonic()
            if len(self.entries) >= MAX_ENTRIES:
                for k in [k for k, (at, _) in self.entries.items() if now - at >= TTL_S]:
                    del self.entries[k]
                    self.locks.pop(k, None)
                while len(self.entries) >= MAX_ENTRIES:  # still full: drop the oldest
                    oldest = min(self.entries, key=lambda k: self.entries[k][0])
                    del self.entries[oldest]
                    self.locks.pop(oldest, None)
            self.entries[key] = (now, value)


_stores: weakref.WeakKeyDictionary[QueryService, _Store] = weakref.WeakKeyDictionary()
_stores_guard = threading.Lock()


def _store(query: QueryService) -> _Store:
    with _stores_guard:
        store = _stores.get(query)
        if store is None:
            store = _stores[query] = _Store()
        return store


def scope_key(principal: Principal) -> tuple[str, str, str]:
    """Who may share a result: same tenant, same warehouses, same permissions."""
    scope = "*" if principal.scope.all else ",".join(sorted(principal.scope.ids))
    return principal.tenant_id, scope, ",".join(sorted(p.value for p in principal.permissions))


def cached[T](query: QueryService, principal: Principal, name: str, args: Hashable, run: Callable[[], T]) -> T:
    """`run()`, or a copy of its result from another caller in the same scope within the last minute."""
    meta = query.tenant_meta(principal.tenant_id)
    as_of = meta.data_as_of.isoformat() if meta.data_as_of else None
    key = (*scope_key(principal), name, args, as_of)
    store = _store(query)
    with store.lock_for(key):
        if not _bypass.get():
            hit = store.get(key)
            if hit is not None:
                query.record(principal, f"analysis:{name}", None, "allow", "ok", reason="cache")
                return copy.deepcopy(hit)  # type: ignore[return-value]
        value = run()
        store.put(key, value)
    return copy.deepcopy(value)


def clear(query: QueryService) -> None:
    """Forget every cached result of this service (tests, and after a mapping change)."""
    with _stores_guard:
        _stores.pop(query, None)
