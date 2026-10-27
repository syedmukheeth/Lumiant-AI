"""`lumiant-synthetic generate` — build the synthetic demo warehouses."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path

from lumiant.core.config import get_settings
from lumiant.synthetic.generator import Generator
from lumiant.synthetic.profiles import PROFILES
from lumiant.synthetic.writer import WriterError, write_duckdb
from lumiant.tenancy.registry import TenantRegistry


def generate_tenant(
    tenant_id: str,
    *,
    registry: TenantRegistry,
    data_dir: Path,
    as_of: date,
    seed: int | None = None,
    n_items: int | None = None,
    months: int | None = None,
) -> tuple[Path, dict[str, int], dict[str, int]]:
    tenant = registry.get(tenant_id)
    if not tenant.synthetic:
        raise SystemExit(f"refusing to generate data for non-synthetic tenant '{tenant_id}'")
    profile = PROFILES[tenant_id]
    dataset = Generator(profile, as_of=as_of, seed=seed, n_items=n_items, months=months).run()
    assert tenant.connection.path is not None
    target = data_dir / tenant.connection.path
    write_duckdb(dataset, tenant, target)
    return target, dataset.counts(), {k: len(v) for k, v in dataset.scenarios.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lumiant-synthetic", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="generate synthetic DuckDB warehouses")
    target = gen.add_mutually_exclusive_group(required=True)
    target.add_argument("--all", action="store_true", help="all synthetic tenants with a profile")
    target.add_argument("--tenant", help="one tenant id")
    gen.add_argument("--seed", type=int)
    gen.add_argument("--as-of", type=date.fromisoformat, help="reference date (default: today, UTC)")
    gen.add_argument("--items", type=int)
    gen.add_argument("--months", type=int)
    args = parser.parse_args(argv)

    settings = get_settings()
    registry = TenantRegistry.load(settings.tenant_config_dir)
    as_of = args.as_of or datetime.now(UTC).date()
    tenant_ids = [t.id for t in registry if t.synthetic and t.id in PROFILES] if args.all else [args.tenant]
    for tenant_id in tenant_ids:
        if tenant_id not in PROFILES:
            print(f"no synthetic profile for tenant '{tenant_id}'", file=sys.stderr)
            return 2
        started = time.perf_counter()
        try:
            path, counts, scenarios = generate_tenant(
                tenant_id,
                registry=registry,
                data_dir=settings.data_dir,
                as_of=as_of,
                seed=args.seed,
                n_items=args.items,
                months=args.months,
            )
        except WriterError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        elapsed = time.perf_counter() - started
        print(
            json.dumps(
                {
                    "tenant": tenant_id,
                    "file": str(path),
                    "seconds": round(elapsed, 1),
                    "rows": counts,
                    "scenarios": scenarios,
                },
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
