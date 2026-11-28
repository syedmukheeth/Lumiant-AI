"""Planning service: one place where the API and the assistant run planning capabilities (no duplicated logic).

Results are JSON-safe (Decimal → string, date → ISO), carry their issues and assumptions, and are recommendations
only: nothing is written to a source system, no purchase order is created or approved, no record is merged.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from lumiant.analyses.cache import cached
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError
from lumiant.planning import scenario
from lumiant.planning.bom import explode
from lumiant.planning.commitment import analyse
from lumiant.planning.duplicates import find_duplicates
from lumiant.planning.loader import LoadedPlanning, load
from lumiant.planning.model import SupplierPolicy
from lumiant.planning.mrp import MrpResult, run_mrp
from lumiant.planning.obsolescence import review
from lumiant.planning.suppliers import compare_suppliers
from lumiant.query.service import QueryService

POLICIES: dict[str, SupplierPolicy] = {
    "balanced": SupplierPolicy("balanced"),
    "urgent": SupplierPolicy("urgent", "fastest"),
    "lowest_cost": SupplierPolicy("lowest_cost", "cheapest"),
    "quality_critical": SupplierPolicy("quality_critical", "quality", max_rejection_pct=Decimal(3)),
}


def jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return format(v.normalize(), "f")
    if isinstance(v, date):
        return v.isoformat()
    if is_dataclass(v) and not isinstance(v, type):
        return jsonable(asdict(v))
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set, frozenset)):
        return [jsonable(x) for x in v]
    if hasattr(v, "value") and isinstance(getattr(v, "value", None), str):
        return v.value
    return v


class PlanningService:
    def __init__(self, query: QueryService) -> None:
        self.query = query

    def _load(self, principal: Principal, today: date | None) -> LoadedPlanning:
        on = today or date.today()
        # Up to ten governed reads (~1.4 s); master data, planning, suppliers and commitments share one load per
        # scope and data timestamp. `cached` returns a deep copy, so callers may change what they get.
        loaded = cached(self.query, principal, "planning_load", on.isoformat(), lambda: load(self.query, principal, on))
        meta = self.query.tenant_meta(principal.tenant_id)
        if meta.stale:
            loaded.issues.append(
                _issue(
                    "stale_data",
                    "warning",
                    "The source data is older than the tenant's freshness limit; check it before deciding.",
                )
            )
        return loaded

    def _record(self, principal: Principal, action: str, dataset: str) -> None:
        self.query.record(principal, f"planning:{action}", dataset, "allow", "ok")

    def _meta(self, loaded: LoadedPlanning) -> dict[str, Any]:
        return {
            "today": loaded.data.today.isoformat(),
            "issues": [jsonable(i) for i in loaded.issues],
            "available": loaded.available,
            "recommendation_only": True,
        }

    # ------------------------------------------------------------------------------------------------ capabilities
    def mrp(self, principal: Principal, today: date | None = None) -> tuple[LoadedPlanning, MrpResult]:
        loaded = self._load(principal, today)
        if not loaded.data.demand:
            raise AppError("analysis_unavailable", "No open customer orders are available in your scope.", 409)
        result = run_mrp(loaded.data)
        self._record(principal, "mrp", "customer_order_line")
        return loaded, result

    def fulfilment(
        self, principal: Principal, *, order_id: str | None = None, today: date | None = None
    ) -> dict[str, Any]:
        loaded, result = self.mrp(principal, today)
        lines = [
            f for f in result.fulfilment(loaded.data.calendar) if order_id is None or f.key.split("/")[0] == order_id
        ]
        if order_id and not lines:
            raise AppError("not_found", f"Order {order_id} is not open in your scope.", 404)
        return {**self._meta(loaded), "lines": jsonable(lines), "issues": jsonable([*loaded.issues, *result.issues])}

    def material_plan(
        self, principal: Principal, *, item_id: str | None = None, today: date | None = None
    ) -> dict[str, Any]:
        loaded, result = self.mrp(principal, today)
        orders = [p for p in result.planned_orders if item_id is None or p.item_id == item_id]
        rows = [
            {
                "planned_order": p.id,
                "item_id": p.item_id,
                "warehouse_id": p.warehouse_id,
                "action": p.action,
                "net": p.net,
                "quantity": p.quantity,
                "excess": p.excess,
                "need": p.need,
                "release": p.release,
                "ready": p.ready,
                "lead_days": p.lead_days,
                "bom": p.bom,
                "for_orders": list(p.pegs),
                "explanation": p.explanation,
                "issues": [i.message for i in p.issues],
            }
            for p in sorted(orders, key=lambda p: (p.release or date.max, p.item_id))
        ]
        excess = [
            {"item_id": i, "warehouse_id": w, "source": s, "reference": r, "quantity": q}
            for i, w, s, r, q in result.excess_supply()
        ]
        return {
            **self._meta(loaded),
            "planned_orders": jsonable(rows),
            "excess_supply": jsonable(excess),
            "issues": jsonable([*loaded.issues, *result.issues]),
        }

    def bom(self, principal: Principal, item_id: str, quantity: Decimal, on: date | None = None) -> dict[str, Any]:
        loaded = self._load(principal, on)
        if item_id not in loaded.data.items:
            raise AppError("not_found", f"Item {item_id} is not in the item master.", 404)
        ex = explode(item_id, quantity, loaded.data.today, loaded.data.boms, loaded.data.items, loaded.data.conversions)
        self._record(principal, "bom", "bom_component")
        return {
            **self._meta(loaded),
            "item_id": item_id,
            "quantity": jsonable(quantity),
            "lines": jsonable(
                [
                    {
                        "component_id": ln.component_id,
                        "quantity": ln.quantity,
                        "level": ln.level,
                        "path": list(ln.path),
                        "bom": f"{ln.bom_id} rev {ln.revision}",
                        "explanation": ln.explanation,
                        "phantom": ln.phantom,
                        "subassembly": ln.exploded,
                    }
                    for ln in ex.lines
                ]
            ),
            "totals": jsonable(ex.totals()),
            "issues": jsonable([*loaded.issues, *ex.issues]),
        }

    def suppliers(
        self,
        principal: Principal,
        item_id: str,
        quantity: Decimal,
        *,
        need_date: date | None,
        policy: str = "balanced",
        today: date | None = None,
    ) -> dict[str, Any]:
        if not principal.has(Permission.COST_READ):
            raise AppError("forbidden_field", "Supplier prices need cost access, which your role does not have.", 403)
        if policy not in POLICIES:
            raise AppError("invalid_request", f"Unknown supplier policy {policy}.", 422)
        loaded = self._load(principal, today)
        cmp = compare_suppliers(
            item_id,
            quantity,
            today=loaded.data.today,
            need_date=need_date,
            offers=loaded.offers,
            suppliers=loaded.suppliers,
            deliveries=loaded.deliveries,
            prices=loaded.prices,
            fx=[],
            policy=POLICIES[policy],
            calendar=loaded.data.calendar,
        )
        self._record(principal, "suppliers", "supplier_item")
        return {
            **self._meta(loaded),
            "item_id": item_id,
            "quantity": jsonable(quantity),
            "need_date": jsonable(need_date),
            "policy": policy,
            "offers": jsonable(cmp.offers),
            "split": jsonable(cmp.split),
            "recommendation": cmp.recommendation,
            "gaps": cmp.gaps,
        }

    def duplicates(self, principal: Principal) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            loaded = self._load(principal, None)
            found = find_duplicates(list(loaded.data.items.values()))  # pairwise text matching, ~0.3 s
            return {**self._meta(loaded), "findings": jsonable(found)}

        out = cached(self.query, principal, "duplicates", date.today().isoformat(), run)
        self._record(principal, "duplicates", "item")
        return out

    def lifecycle(self, principal: Principal, today: date | None = None) -> dict[str, Any]:
        if not self.query.mapping(principal.tenant_id).has_ref("item", "critical"):
            # Without criticality an item could be called obsolete from inactivity alone (scenario 20): refuse.
            raise AppError(
                "analysis_unavailable",
                "Lifecycle review needs item criticality (e.g. critical spares), which this tenant does not provide.",
                409,
            )
        loaded = self._load(principal, today)
        mrp = run_mrp(loaded.data) if loaded.data.demand else None
        findings = review(
            loaded.data.items,
            loaded.on_hand,
            loaded.last_issue,
            today=loaded.data.today,
            boms=loaded.data.boms,
            mrp=mrp,
        )
        self._record(principal, "lifecycle", "item")
        return {**self._meta(loaded), "findings": jsonable(findings)}

    def commitments(self, principal: Principal, today: date | None = None) -> dict[str, Any]:
        """Open order lines that are late or cannot be dated: the candidates for commitment protection."""
        if not principal.has(Permission.COST_READ):  # rows carry order value
            raise AppError("forbidden_field", "Commitment protection shows order value, which needs cost access.", 403)
        loaded, result = self.mrp(principal, today)
        lines = [f for f in result.fulfilment(loaded.data.calendar) if not f.on_time]
        by_key = {d.key: d for d in loaded.data.demand}
        rows = [
            {
                "key": f.key,
                "item_id": f.item_id,
                "customer_id": f.customer_id,
                "quantity": f.quantity,
                "due": f.due,
                "delivery": f.delivery,
                "late_days": f.late_days,
                "order_value": by_key[f.key].value if f.key in by_key else None,
                "currency": by_key[f.key].currency if f.key in by_key else "",
            }
            for f in lines
        ]
        return {**self._meta(loaded), "at_risk": jsonable(rows)}

    def commitment(self, principal: Principal, order_key: str, today: date | None = None) -> dict[str, Any]:
        """Customer Commitment Protection analysis for one order line (needs cost access: prices and order value)."""
        if not principal.has(Permission.COST_READ):
            raise AppError(
                "forbidden_field",
                "Commitment protection uses supplier prices and order value, which need cost access.",
                403,
            )
        loaded = self._load(principal, today)
        analysis = analyse(
            loaded.data,
            order_key,
            offers=loaded.offers,
            suppliers=loaded.suppliers,
            deliveries=loaded.deliveries,
            prices=loaded.prices,
        )
        if analysis is None:
            raise AppError("not_found", f"Order line {order_key} is not open in your scope.", 404)
        self._record(principal, "commitment", "customer_order_line")
        return {**self._meta(loaded), **jsonable(analysis)}

    def assess(self, principal: Principal, question: str) -> dict[str, Any]:
        loaded = self._load(principal, None)
        a = scenario.assess(question, loaded.available)
        if a.capability_gaps:
            # Recorded as a candidate new capability (audit log), never answered as if it were solved.
            self.query.record(
                principal,
                "planning:capability_gap",
                "scenario",
                "allow",
                "gap",
                reason="capability_gap",  # a code: the audit column is 64 characters (enforced on PostgreSQL)
                fields=tuple(a.capabilities),
            )
        return {**self._meta(loaded), **jsonable(a)}


def _issue(code: str, severity: str, message: str) -> Any:
    from lumiant.planning.model import Issue, Severity

    return Issue(code, Severity(severity), message)
