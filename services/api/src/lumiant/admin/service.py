"""Onboarding and administration: schema discovery, capability matrix, reconciliation against customer reports.

All of this reads metadata or runs through the normal secured query path; nothing here writes to a source system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from lumiant.audit.store import AuditEvent
from lumiant.auth.principal import Principal
from lumiant.connectors.base import ConnectorError
from lumiant.core.errors import AppError
from lumiant.mapping.resolver import SourceObject, TenantMapping
from lumiant.query.service import QueryService
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
    drifted = totals["missing_tables"] + totals["missing_columns"] + totals["type_mismatches"]
    return {
        "healthy": connector.health(),
        "datasets": datasets,
        "totals": totals,
        "verdict": "ok" if drifted == 0 else "drift",
        "note": "Unmapped columns are candidates for review; the platform never assumes two similarly named columns mean the same thing.",
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
    out: list[dict[str, Any]] = []
    for cap in CAPABILITIES:
        missing: list[str] = []
        for ds, fields in cap.needs.items():
            if not mapping.is_mapped(ds):
                missing.append(f"dataset {ds}")
                continue
            missing += [f"{ds}.{f}" for f in fields if mapping.field(ds, f) is None]
        if cap.id == "item_code_rules" and mapping.tenant.item_coding is None:
            missing.append("item_coding rules")
        available = not missing
        out.append(
            {
                "id": cap.id,
                "title": cap.title,
                "available": available,
                "missing": missing,
                "explanation": None
                if available
                else "Not available: " + ", ".join(missing) + " is not mapped for this tenant.",
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
        result = discover(mapping, connector)
        self.query.record(principal, "admin:schema_discovery", None, "allow", "ok", rows=len(result["datasets"]))
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
