"""Validation harness for a mapping (V2, docs/AI_SCHEMA_DISCOVERY.md §9 step 2: "highest value; do this first").

Structural checks that prove a mapping can be trusted before anyone relies on its figures: keys are unique (the grain
is right), facts point at master records that exist (no orphans), and required fields are filled. Counts only; no
row values leave the source. Runs as an administrator, without warehouse scope, through the connector.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa

from lumiant.connectors.base import ConnectorError
from lumiant.mapping.resolver import TenantMapping

# (dataset, key fields): each key combination must appear once
GRAINS = (
    ("item", ("item_id",)),
    ("warehouse", ("warehouse_id",)),
    ("lot", ("lot_id",)),
    ("supplier", ("supplier_id",)),
    ("reorder_policy", ("item_id", "warehouse_id")),
    ("item_warehouse", ("item_id", "warehouse_id")),
)
# (fact dataset, field, master dataset, master field): every fact value must exist in the master
REFERENCES = (
    ("stock_balance", "item_id", "item", "item_id"),
    ("stock_balance", "warehouse_id", "warehouse", "warehouse_id"),
    ("stock_balance", "lot_id", "lot", "lot_id"),
    ("inventory_transaction", "item_id", "item", "item_id"),
    ("reorder_policy", "item_id", "item", "item_id"),
    ("purchase_record", "supplier_id", "supplier", "supplier_id"),
)
REQUIRED = ("stock_balance", "inventory_transaction", "item")


def _count(connector: Any, mapping: TenantMapping, stmt: sa.Select[Any]) -> int:
    raw = connector.execute(stmt, fetch_limit=1, timeout_s=mapping.tenant.policies.query_timeout_s)
    return int(raw.rows[0][0] or 0)


def _mapped(mapping: TenantMapping, dataset: str, *fields: str) -> bool:
    return mapping.is_mapped(dataset) and all(mapping.field(dataset, f) is not None for f in fields)


def run_validation(mapping: TenantMapping, connector: Any) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(check_id: str, title: str, count: int | None, total: int | None, detail: str) -> None:
        status = "not_run" if count is None else "ok" if count == 0 else "issue"
        checks.append(
            {"id": check_id, "title": title, "status": status, "count": count, "total": total, "detail": detail}
        )

    def safe(fn: Any) -> int | None:
        try:
            return int(fn())
        except (ConnectorError, sa.exc.DBAPIError, IndexError):
            return None

    for dataset, keys in GRAINS:
        if not _mapped(mapping, dataset, *keys):
            continue
        t = mapping.table(dataset).alias("t")
        cols = [mapping.column_expr(dataset, k, t) for k in keys]
        total = safe(lambda t=t: _count(connector, mapping, sa.select(sa.func.count()).select_from(t)))
        groups = sa.select(*cols).select_from(t).group_by(*cols).having(sa.func.count() > 1).subquery("dup")
        dupes = safe(lambda groups=groups: _count(connector, mapping, sa.select(sa.func.count()).select_from(groups)))
        add(
            f"unique_{dataset}",
            f"{dataset.replace('_', ' ').capitalize()}: one row per {' + '.join(keys)}",
            dupes,
            total,
            "Key values that appear more than once. Duplicates double-count figures that join on this key.",
        )

    for fact, ffield, master, mfield in REFERENCES:
        if not (_mapped(mapping, fact, ffield) and _mapped(mapping, master, mfield)):
            continue
        f = mapping.table(fact).alias("f")
        m = mapping.table(master).alias("m")
        fcol, mcol = mapping.column_expr(fact, ffield, f), mapping.column_expr(master, mfield, m)
        missing = (
            sa.select(sa.func.count())
            .select_from(f.outerjoin(m, fcol == mcol))
            .where(fcol.is_not(None), mcol.is_(None))
        )
        total = safe(
            lambda f=f, fcol=fcol: _count(
                connector, mapping, sa.select(sa.func.count()).select_from(f).where(fcol.is_not(None))
            )
        )
        add(
            f"orphan_{fact}_{ffield}",
            f"{fact.replace('_', ' ').capitalize()} rows whose {ffield} is not in {master.replace('_', ' ')}",
            safe(lambda missing=missing: _count(connector, mapping, missing)),
            total,
            "Rows pointing at a master record that does not exist; their figures cannot be described or grouped.",
        )

    for dataset in REQUIRED:
        if not mapping.is_mapped(dataset):
            continue
        t = mapping.table(dataset).alias("t")
        required = [
            n
            for n, fd in mapping.fields(dataset).items()
            if fd.required and not fd.computed and mapping.field(dataset, n)
        ]
        if not required:
            continue
        cond = sa.or_(*(mapping.column_expr(dataset, n, t).is_(None) for n in required))
        add(
            f"required_{dataset}",
            f"{dataset.replace('_', ' ').capitalize()} rows missing a required field",
            safe(
                lambda t=t, cond=cond: _count(connector, mapping, sa.select(sa.func.count()).select_from(t).where(cond))
            ),
            safe(lambda t=t: _count(connector, mapping, sa.select(sa.func.count()).select_from(t))),
            f"Required: {', '.join(required)}. Such rows are left out of totals.",
        )
    return checks
