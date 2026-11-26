"""Onboarding and administration: schema discovery, capability matrix, reconciliation against customer reports.

All of this reads metadata or runs through the normal secured query path; nothing here writes to a source system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import sqlalchemy as sa

from lumiant.audit.store import AuditEvent
from lumiant.auth.principal import Principal
from lumiant.connectors.base import ConnectorError
from lumiant.core.errors import AppError
from lumiant.mapping.resolver import SourceObject, TenantMapping
from lumiant.query.compiler import condition
from lumiant.query.plan import Op
from lumiant.query.service import QueryService
from lumiant.query.sql_guard import check_sql
from lumiant.reports.service import ReportService

_NUMERIC_HINTS = ("INT", "DEC", "NUM", "FLOAT", "DOUBLE", "REAL", "MONEY")
_DATE_HINTS = ("DATE", "TIME")


def type_category(sql_type: str) -> str:
    t = sql_type.upper()
    if "BOOL" in t:
        return "boolean"
    if any(h in t for h in _DATE_HINTS):
        return "date"
    if any(h in t for h in _NUMERIC_HINTS):
        return "number"
    return "text"


_CANONICAL_CATEGORY = {
    "string": "text",
    "integer": "number",
    "decimal": "number",
    "date": "date",
    "datetime": "date",
    "boolean": "boolean",
}


def discover(mapping: TenantMapping, connector: Any) -> dict[str, Any]:
    """Compare what the tenant mapping expects with what the source actually exposes."""
    datasets: list[dict[str, Any]] = []
    totals = {"missing_tables": 0, "missing_columns": 0, "type_mismatches": 0, "unmapped_columns": 0}
    for ds_name, ds_map in mapping.tenant.datasets.items():
        src = SourceObject.parse(ds_map.source)
        entry: dict[str, Any] = {
            "dataset": ds_name,
            "source": ds_map.source,
            "status": "ok",
            "problems": [],
            "unmapped": [],
        }
        try:
            exists = connector.has_table(src.schema, src.name)
        except ConnectorError:
            entry["status"] = "unavailable"
            entry["problems"].append({"kind": "source_unavailable"})
            datasets.append(entry)
            continue
        if not exists:
            entry["status"] = "missing_table"
            entry["problems"].append({"kind": "missing_table", "source": ds_map.source})
            totals["missing_tables"] += 1
            datasets.append(entry)
            continue
        physical = {c.name.lower(): c for c in connector.describe(src.schema, src.name)}
        mapped_cols: set[str] = set()
        for canonical in mapping.fields(ds_name):
            fdef = mapping.field(ds_name, canonical)
            if fdef is None or fdef.computed:
                continue
            column = mapping.physical_column(ds_name, canonical)
            mapped_cols.add(column.lower())
            found = physical.get(column.lower())
            if found is None:
                entry["problems"].append({"kind": "missing_column", "field": canonical, "column": column})
                totals["missing_columns"] += 1
            elif type_category(found.type) != _CANONICAL_CATEGORY[fdef.type.value]:
                entry["problems"].append(
                    {
                        "kind": "type_mismatch",
                        "field": canonical,
                        "column": column,
                        "expected": fdef.type.value,
                        "found": found.type,
                    }
                )
                totals["type_mismatches"] += 1
        for name, col in physical.items():
            if name not in mapped_cols and not name.startswith("_"):
                entry["unmapped"].append({"column": col.name, "type": col.type, "category": type_category(col.type)})
                totals["unmapped_columns"] += 1
        if entry["problems"]:
            entry["status"] = "drift"
        datasets.append(entry)
    note = "Unmapped columns are candidates for review; the platform never assumes two similarly named columns mean the same thing."
    unconfigured: list[str] = []
    no_warehouse = 0
    check_failed = False
    stock = next((d for d in datasets if d["dataset"] == _STOCK), None)
    column_missing = stock is not None and any(
        p["kind"] == "missing_column" and p.get("field") == "warehouse_id" for p in stock["problems"]
    )
    if stock is not None and stock["status"] in ("ok", "drift") and not column_missing:
        try:
            unconfigured, truncated = unconfigured_warehouses(mapping, connector)
            no_warehouse = rows_without_warehouse(mapping, connector)
        except ConnectorError as exc:
            # An unverified check must not read as ok.
            check_failed = True
            stock["status"] = "drift"
            stock["problems"].append({"kind": "warehouse_check_failed", "field": "warehouse_id", "reason": exc.code})
        else:
            if truncated:
                note += f" Only the first {len(unconfigured)} unconfigured warehouses are listed."
    totals["unconfigured_warehouses"] = len(unconfigured)
    totals["rows_without_warehouse"] = no_warehouse
    drifted = totals["missing_tables"] + totals["missing_columns"] + totals["type_mismatches"]
    drifted += len(unconfigured) + no_warehouse + check_failed
    return {
        "healthy": connector.health(),
        "datasets": datasets,
        "totals": totals,
        "unconfigured_warehouses": unconfigured,
        "rows_without_warehouse": no_warehouse,
        "verdict": "ok" if drifted == 0 else "drift",
        "note": note,
    }


_STOCK = "stock_balance"
_UNCONFIGURED_LIMIT = 500


def _run(mapping: TenantMapping, connector: Any, stmt: sa.Select[Any], fetch_limit: int) -> list[tuple[Any, ...]]:
    """Execute an admin check read through the same SQL guard and timeout as every other query."""
    check_sql(QueryService.render(stmt, connector.dialect), connector.dialect_name, mapping.physical_tables())
    raw = connector.execute(stmt, fetch_limit=fetch_limit, timeout_s=mapping.tenant.policies.query_timeout_s)
    return [tuple(r) for r in raw.rows]


def rows_without_warehouse(mapping: TenantMapping, connector: Any) -> int:
    """Stock rows with no warehouse id.

    Like an unconfigured warehouse, such a row is counted in every total for users who see all warehouses and is
    invisible to everyone else, since no warehouse scope can match an empty id.
    """
    if mapping.field(_STOCK, "warehouse_id") is None:
        return 0
    warehouse = mapping.column_expr(_STOCK, "warehouse_id", mapping.table(_STOCK))
    stmt = sa.select(sa.func.count().label("rows")).select_from(mapping.table(_STOCK)).where(warehouse.is_(None))
    rows = _run(mapping, connector, stmt, fetch_limit=1)
    return int(rows[0][0]) if rows else 0


def unconfigured_warehouses(mapping: TenantMapping, connector: Any) -> tuple[list[str], bool]:
    """Warehouse ids in the source stock data that the tenant configuration does not list.

    Warehouse scope ids come only from the configuration, so such a warehouse is counted in every total for users
    who see all warehouses and is invisible to everyone else. The condition is the scope filter's own IN test,
    negated, so "unconfigured" means exactly "unreachable through warehouse scope". Returns the sorted ids (at most
    `_UNCONFIGURED_LIMIT`) and whether more exist. Rows without a warehouse id are counted by
    `rows_without_warehouse`.
    """
    if mapping.field(_STOCK, "warehouse_id") is None:
        return [], False
    configured = sorted({w.id for w in mapping.tenant.warehouses})
    warehouse = mapping.column_expr(_STOCK, "warehouse_id", mapping.table(_STOCK)).label("warehouse_id")
    stmt = (
        sa.select(warehouse).where(condition(warehouse.element, Op.NOT_IN, configured)).distinct().order_by(warehouse)
    )
    rows = _run(mapping, connector, stmt, fetch_limit=_UNCONFIGURED_LIMIT + 1)
    ids = sorted(str(r[0]) for r in rows if r[0] is not None)
    return ids[:_UNCONFIGURED_LIMIT], len(ids) > _UNCONFIGURED_LIMIT


def for_scope(result: dict[str, Any], principal: Principal) -> dict[str, Any]:
    """Unconfigured warehouse ids are listed only to someone who sees every warehouse.

    An administrator limited to some warehouses still gets the non-ok verdict and the count, never the ids.
    """
    if principal.scope.all or not result["unconfigured_warehouses"]:
        return result
    return {
        **result,
        "unconfigured_warehouses": [],
        "note": result["note"]
        + " Warehouses missing from the tenant configuration were found; an administrator who sees all warehouses can list them.",
    }


@dataclass(frozen=True)
class Capability:
    id: str
    title: str
    needs: dict[str, tuple[str, ...]]
    optional: dict[str, tuple[str, ...]] | None = None


CAPABILITIES = (
    Capability(
        "inventory_value",
        "Inventory value and dashboards",
        {"stock_balance": ("item_id", "warehouse_id", "quantity", "uom", "valuation_price", "currency")},
    ),
    Capability(
        "below_reorder",
        "Below-reorder analysis",
        {
            "reorder_policy": ("item_id", "warehouse_id", "reorder_level"),
            "stock_balance": ("item_id", "warehouse_id", "quantity", "uom"),
            "item": ("item_id", "base_uom"),
        },
    ),
    Capability(
        "excess_stock",
        "Excess stock analysis",
        {
            "reorder_policy": ("item_id", "warehouse_id", "max_stock"),
            "stock_balance": ("item_id", "warehouse_id", "quantity", "uom"),
            "item": ("item_id", "base_uom"),
        },
    ),
    Capability(
        "dormant_stock",
        "Dormant and slow-moving stock",
        {
            "stock_balance": ("item_id", "warehouse_id", "quantity", "uom"),
            "inventory_transaction": ("item_id", "warehouse_id", "txn_type", "posting_date"),
        },
    ),
    Capability(
        "expiring_lots", "Expiring lots", {"stock_balance": ("lot_id", "quantity"), "lot": ("lot_id", "expiry_date")}
    ),
    Capability(
        "cost_comparison",
        "Cost comparison (moving average, FIFO, latest receipt)",
        {
            "inventory_transaction": ("txn_id", "txn_type", "quantity", "unit_cost", "posting_date", "uom", "currency"),
            "stock_balance": ("quantity", "valuation_price"),
        },
    ),
    Capability(
        "latest_purchase_price",
        "Latest valid purchase price",
        {"purchase_record": ("po_id", "order_date", "status", "unit_price")},
    ),
    Capability("lot_cost", "Lot cost", {"lot": ("lot_id", "receipt_date", "unit_cost"), "stock_balance": ("lot_id",)}),
    Capability(
        "abc_compare",
        "Computed vs assigned ABC",
        {"stock_balance": ("item_id", "quantity", "valuation_price"), "item": ("item_id", "abc_class")},
    ),
    Capability(
        "special_storage",
        "Special storage requirements",
        {"item": ("item_id", "storage_temp_min", "flammability_class")},
    ),
    Capability("item_code_rules", "Item-code validation", {}),
    Capability(
        "fifo_pick",
        "FIFO pick suggestion (lot receipt dates)",
        {"lot": ("lot_id", "receipt_date"), "stock_balance": ("lot_id", "quantity")},
    ),
)


def capability_matrix(mapping: TenantMapping) -> list[dict[str, Any]]:
    hints = mapping.tenant.source_hints
    out: list[dict[str, Any]] = []
    for cap in CAPABILITIES:
        missing: list[str] = []
        for ds, fields in cap.needs.items():
            if not mapping.is_mapped(ds):
                missing.append(f"dataset {ds}")
                continue
            missing += [f"{ds}.{f}" for f in fields if mapping.field(ds, f) is None]
        needs_file: list[str] = []
        for key in missing:
            key = key.removeprefix("dataset ")
            text = hints.get(key) or hints.get(key.partition(".")[0])
            if text and text not in needs_file:
                needs_file.append(text)
        if cap.id == "item_code_rules" and mapping.tenant.item_coding is None:
            missing.append("item_coding rules")
        available = not missing
        explanation = None
        if not available:
            explanation = "Not available: " + ", ".join(missing) + " is not mapped for this tenant."
            if needs_file:
                explanation += " Needs: " + "; ".join(needs_file) + "."
        out.append(
            {
                "id": cap.id,
                "title": cap.title,
                "available": available,
                "missing": missing,
                "needs_file": needs_file,
                "explanation": explanation,
            }
        )
    return out


def _dec(text: str) -> Decimal:
    try:
        d = Decimal(str(text).replace(",", "").strip())
    except InvalidOperation as exc:
        raise AppError("invalid_request", f"'{text}' is not a number.", 422) from exc
    if not d.is_finite():
        raise AppError("invalid_request", f"'{text}' is not a number.", 422)
    return d


class AdminService:
    def __init__(self, query: QueryService, reports: ReportService) -> None:
        self.query = query
        self.reports = reports

    def discovery(self, principal: Principal) -> dict[str, Any]:
        mapping = self.query.mapping(principal.tenant_id)
        connector = self.query.connectors.get(principal.tenant_id)
        result = for_scope(discover(mapping, connector), principal)
        self.query.record(
            principal,
            "admin:schema_discovery",
            None,
            "allow",
            "ok",
            fields=(f"{_STOCK}.warehouse_id",),
            rows=len(result["datasets"]),
        )
        return result

    def capabilities(self, principal: Principal) -> list[dict[str, Any]]:
        return capability_matrix(self.query.mapping(principal.tenant_id))

    def audit(
        self, principal: Principal, *, limit: int, offset: int, decision: str | None, prefix: str | None
    ) -> list[dict[str, Any]]:
        events = self.query.audit.search(
            principal.tenant_id, limit=limit, offset=offset, decision=decision, action_prefix=prefix
        )
        return [_event(e) for e in events]

    def reconcile(self, principal: Principal, rows: list[dict[str, str]], tolerance: str) -> dict[str, Any]:
        tol = _dec(tolerance)
        if tol < 0:
            raise AppError("invalid_request", "Tolerance cannot be negative.", 422)
        report = self.reports.build("value_by_warehouse", principal, {}, limit=1000)
        computed = {
            (str(r["warehouse_id"]), str(r["currency"])): Decimal(str(r["value"]))
            for r in report["rows"]
            if r.get("value") is not None
        }
        customer: dict[tuple[str, str], Decimal] = {}
        for row in rows:
            key = (str(row["warehouse_id"]).strip(), str(row["currency"]).strip().upper())
            customer[key] = customer.get(key, Decimal(0)) + _dec(row["value"])
        lines: list[dict[str, Any]] = []
        for key in sorted(set(computed) | set(customer)):
            ours, theirs = computed.get(key), customer.get(key)
            if ours is None:
                status, diff = "missing_in_platform", None
            elif theirs is None:
                status, diff = "missing_in_customer_report", None
            else:
                diff = ours - theirs
                status = "match" if abs(diff) <= tol else "variance"
            lines.append(
                {
                    "warehouse_id": key[0],
                    "currency": key[1],
                    "platform": None if ours is None else format(ours, "f"),
                    "customer": None if theirs is None else format(theirs, "f"),
                    "difference": None if diff is None else format(diff, "f"),
                    "status": status,
                }
            )
        counts: dict[str, int] = {}
        for ln in lines:
            counts[ln["status"]] = counts.get(ln["status"], 0) + 1
        passed = bool(lines) and set(counts) == {"match"}
        self.query.record(
            principal,
            "admin:reconciliation",
            "stock_balance",
            "allow",
            "ok",
            rows=len(lines),
            reason="pass" if passed else "fail",
        )
        return {
            "report": "value_by_warehouse",
            "tolerance": format(tol, "f"),
            "lines": lines,
            "counts": counts,
            "passed": passed,
            "ran_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "synthetic": report["metadata"]["synthetic"],
            "note": "Go-live gate: every warehouse and currency must match the customer's authoritative report within the tolerance. Amounts are compared per currency, never converted.",
        }


def _event(e: AuditEvent) -> dict[str, Any]:
    return {
        "id": e.id,
        "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        "user_id": e.user_id,
        "action": e.action,
        "dataset": e.dataset,
        "fields": e.fields,
        "decision": e.decision,
        "reason": e.reason_code,
        "rows": e.row_count,
        "duration_ms": e.duration_ms,
        "status": e.status,
        "request_id": e.request_id,
    }
