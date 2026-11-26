"""Overview load benchmark: source queries and response times for the requests a cold Overview page sends.

Runs the API in-process (no network, no browser) against a freshly generated full-size synthetic tenant, signs in as
a demo user, and replays the Overview's request set. Every source query is counted by wrapping the DuckDB connector,
so the numbers show how much repeated work one page load causes. Synthetic data only.

    uv run python benchmarks/overview_load.py --out ../../var/bench/overview.json

Record the printed summary in docs/logs/TEST_RUNS.md. Timings depend on the machine; query counts do not.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from lumiant.connectors.duckdb_connector import DuckDBConnector
from lumiant.core.config import BASE_DIR, Settings
from lumiant.main import create_app
from lumiant.synthetic.cli import generate_tenant
from lumiant.tenancy.registry import TenantRegistry

CSRF = {"X-Requested-With": "lumiant"}

# The requests a cold Overview sends, in page order (apps/web: app shell, KPI strip, area board, value bars,
# insights feed, below-reorder panel). Identical React Query keys are sent once, so they appear once here.
OVERVIEW = [
    "/api/auth/me",
    "/api/meta/tenant",
    "/api/metrics",
    "/api/metrics/inventory_value_total",
    "/api/metrics/items_in_stock",
    "/api/metrics/stock_lines",
    "/api/analyses/below-reorder?offset=0&limit=12",  # KPI, area board and panel share this key (V0)
    "/api/metrics/inventory_value_by_warehouse",
    "/api/metrics/inventory_value_by_item_group",
    "/api/metrics/inventory_value_by_abc",
    "/api/metrics/inventory_value_by_stage",
    "/api/analyses/excess-stock?limit=1",
    "/api/analyses/dormant?limit=1&days=180",
    "/api/analyses/expiring-lots?limit=1&days=60",
    "/api/analyses/data-quality",
    "/api/insights",
]

# Other heavy endpoints worth tracking (not part of the Overview).
OTHERS = [
    "/api/inventory/filters",
    "/api/inventory/balances?limit=50",
    "/api/analyses/abc?a=0.8&b=0.95",
]


class _Counter:
    def __init__(self) -> None:
        self.count = 0


@contextmanager
def counted_queries() -> Iterator[_Counter]:
    """Count every statement the DuckDB connector executes while the block runs."""
    counter = _Counter()
    original = DuckDBConnector.execute

    def wrapped(self: DuckDBConnector, *args: Any, **kwargs: Any) -> Any:
        counter.count += 1
        return original(self, *args, **kwargs)

    DuckDBConnector.execute = wrapped  # type: ignore[method-assign]
    try:
        yield counter
    finally:
        DuckDBConnector.execute = original  # type: ignore[method-assign]


def _settings(data_dir: Path) -> Settings:
    db = data_dir / "app.db"
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="bench-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=f"sqlite:///{db.as_posix()}",
        log_level="WARNING",
    )


def _call(client: TestClient, url: str) -> tuple[int, float]:
    start = time.perf_counter()
    r = client.get(url)
    return r.status_code, (time.perf_counter() - start) * 1000


def run(tenant: str, user: str, as_of: date, warm_runs: int) -> dict[str, Any]:
    registry = TenantRegistry.load(BASE_DIR / "config" / "tenants")
    with tempfile.TemporaryDirectory(prefix="lumiant-bench-") as tmp:
        data_dir = Path(tmp)
        generate_tenant(tenant, registry=registry, data_dir=data_dir, as_of=as_of)
        with TestClient(create_app(_settings(data_dir))) as client:
            r = client.post("/api/auth/dev-login", json={"username": user}, headers=CSRF)
            r.raise_for_status()

            cold: dict[str, dict[str, Any]] = {}
            with counted_queries() as total:
                for url in OVERVIEW + OTHERS:
                    with counted_queries() as one:
                        status, ms = _call(client, url)
                    cold[url] = {"status": status, "queries": one.count, "ms": round(ms, 1)}
            overview_queries = sum(cold[u]["queries"] for u in OVERVIEW)

            warm: dict[str, list[float]] = {u: [] for u in OVERVIEW + OTHERS}
            for _ in range(warm_runs):
                for url in OVERVIEW + OTHERS:
                    warm[url].append(_call(client, url)[1])

    def pct(values: list[float], q: float) -> float:
        ordered = sorted(values)
        return round(ordered[min(len(ordered) - 1, int(q * len(ordered)))], 1)

    endpoints = {
        url: {
            **cold[url],
            "warm_p50_ms": round(statistics.median(warm[url]), 1) if warm[url] else None,
            "warm_p95_ms": pct(warm[url], 0.95) if warm[url] else None,
        }
        for url in OVERVIEW + OTHERS
    }
    return {
        "tenant": tenant,
        "user": user,
        "as_of": as_of.isoformat(),
        "warm_runs": warm_runs,
        "overview_requests": len(OVERVIEW),
        "overview_source_queries": overview_queries,
        "overview_cold_ms": round(sum(cold[u]["ms"] for u in OVERVIEW), 1),
        "all_source_queries": total.count,
        "endpoints": endpoints,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tenant", default="demo-alpha")
    parser.add_argument("--user", default="alpha.admin")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    parser.add_argument("--warm-runs", type=int, default=10)
    parser.add_argument("--out", type=Path, help="write the full result as JSON here")
    args = parser.parse_args()

    result = run(args.tenant, args.user, args.as_of, args.warm_runs)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"{result['tenant']} as {result['user']}, data as of {result['as_of']}, {result['warm_runs']} warm runs")
    print(
        f"Overview: {result['overview_requests']} requests, {result['overview_source_queries']} source queries, "
        f"{result['overview_cold_ms']} ms cold (sum)"
    )
    print(f"{'endpoint':58} {'st':>3} {'q':>4} {'cold':>8} {'p50':>8} {'p95':>8}")
    for url, e in result["endpoints"].items():
        print(f"{url:58} {e['status']:>3} {e['queries']:>4} {e['ms']:>8} {e['warm_p50_ms']:>8} {e['warm_p95_ms']:>8}")


if __name__ == "__main__":
    main()
