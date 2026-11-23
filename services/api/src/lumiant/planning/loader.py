"""Canonical datasets → planning inputs, read only through the query engine.

Every read is a validated `QueryPlan`, so tenant isolation, warehouse scope (orders, stock, purchase lines, item
plant data), cost permissions (supplier prices) and the audit log apply before the engine sees anything. Master data
(items, BOMs, alternates, suppliers) is not warehouse-scoped. A dataset that is not mapped is simply absent and is
reported through `available`; truncated reads become warnings instead of silent gaps.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.core.errors import AppError
from lumiant.planning.model import (
    ONE,
    ZERO,
    AlternateRule,
    Bom,
    BomLine,
    Certification,
    DeliveryRecord,
    DemandLine,
    Issue,
    Item,
    PlanningData,
    PlanningPolicy,
    PriceRecord,
    Severity,
    StockLine,
    Supplier,
    SupplierOffer,
    Supply,
)
from lumiant.query.plan import QueryPlan
from lumiant.query.service import QueryService

MAX_PAGES = 20
CLOSED = {"CANCELLED", "CANCELED", "CLOSED", "COMPLETED", "DELIVERED"}


@dataclass
class LoadedPlanning:
    data: PlanningData
    suppliers: dict[str, Supplier] = field(default_factory=dict)
    offers: list[SupplierOffer] = field(default_factory=list)
    deliveries: list[DeliveryRecord] = field(default_factory=list)
    prices: list[PriceRecord] = field(default_factory=list)
    last_issue: dict[str, date | None] = field(default_factory=dict)
    on_hand: dict[str, Decimal] = field(default_factory=dict)
    available: dict[str, int] = field(default_factory=dict)  # scenario data keys → record counts
    issues: list[Issue] = field(default_factory=list)
    can_see_cost: bool = False


def _dec(v: Any) -> Decimal | None:
    return None if v is None else Decimal(str(v))


def _lot_rule(v: Any) -> Literal["lot_for_lot", "fixed", "min_qty", "multiple"]:
    s = str(v or "")
    if s == "fixed":
        return "fixed"
    if s == "min_qty":
        return "min_qty"
    if s == "multiple":
        return "multiple"
    return "lot_for_lot"


def _procurement(v: Any) -> Literal["buy", "make"] | None:
    """make / buy per plant; SAP BESKZ E (in-house) and F (external) are accepted too; X (both) plans as make."""
    s = str(v or "").strip().lower()
    if s in ("make", "e", "x", "both", "manufacture"):
        return "make"
    if s in ("buy", "f", "purchase"):
        return "buy"
    return None


class _Reader:
    def __init__(self, query: QueryService, principal: Principal) -> None:
        self.q, self.p = query, principal
        self.mapping = query.mapping(principal.tenant_id)
        self.max_rows = self.mapping.tenant.policies.max_rows
        self.issues: list[Issue] = []

    def mapped(self, dataset: str) -> bool:
        return self.mapping.is_mapped(dataset)

    def rows(
        self, dataset: str, fields: list[str], filters: list[dict[str, Any]] | None = None
    ) -> list[dict[str, Any]]:
        if not self.mapped(dataset):
            return []
        dims = [f for f in fields if self.mapping.has_ref(dataset, f)]
        out: list[dict[str, Any]] = []
        for page in range(MAX_PAGES):
            plan = QueryPlan.model_validate(
                {
                    "dataset": dataset,
                    "dimensions": dims,
                    "filters": filters or [],
                    "limit": self.max_rows,
                    "offset": page * self.max_rows,
                }
            )
            res = self.q.run_plan(plan, self.p, action=f"planning:load:{dataset}")
            out += res.rows
            if len(res.rows) < self.max_rows:
                return out
        self.issues.append(
            Issue(
                "data_truncated",
                Severity.WARNING,
                f"Only the first {len(out)} {dataset} records were read; planning may be incomplete.",
                None,
                dataset,
            )
        )
        return out


def load(query: QueryService, principal: Principal, today: date) -> LoadedPlanning:
    if not principal.has(Permission.INVENTORY_READ):
        raise AppError("forbidden", "Your role cannot read inventory data.", 403)
    r = _Reader(query, principal)
    can_cost = principal.has(Permission.COST_READ)

    # ---------------------------------------------------------------- items and plant settings
    plant = r.rows(
        "item_warehouse",
        [
            "item_id",
            "warehouse_id",
            "procurement_type",
            "phantom",
            "lead_days",
            "receiving_days",
            "inspection_days",
            "safety_stock",
            "lot_rule",
            "lot_size",
            "min_lot",
            "lot_multiple",
        ],
    )
    make = {
        row["item_id"] for row in plant if str(row.get("procurement_type") or "").lower() in ("make", "both", "e", "x")
    }
    phantom = {row["item_id"] for row in plant if row.get("phantom")}
    items: dict[str, Item] = {}
    for row in r.rows(
        "item",
        [
            "item_id",
            "description",
            "base_uom",
            "item_group",
            "inventory_stage",
            "status",
            "critical",
            "lifecycle_status",
            "superseded_by",
            "manufacturer",
            "mpn",
        ],
    ):
        iid = str(row["item_id"])
        items[iid] = Item(
            iid,
            str(row.get("description") or ""),
            str(row.get("base_uom") or ""),
            str(row.get("item_group") or ""),
            str(row.get("inventory_stage") or ""),
            "make" if iid in make else "buy",
            iid in phantom,
            str(row.get("status") or "ACTIVE"),
            bool(row.get("critical")),
            (row.get("lifecycle_status") or "active")
            if row.get("lifecycle_status") in ("active", "superseded", "discontinued")
            else "active",
            row.get("superseded_by"),
            str(row.get("manufacturer") or ""),
            str(row.get("mpn") or ""),
        )
    policies = [
        PlanningPolicy(
            str(row["item_id"]),
            str(row["warehouse_id"]),
            _lot_rule(row.get("lot_rule")),
            _dec(row.get("lot_size")),
            _dec(row.get("min_lot")),
            _dec(row.get("lot_multiple")),
            _dec(row.get("safety_stock")) or ZERO,
            row.get("lead_days"),
            int(row.get("receiving_days") or 0),
            int(row.get("inspection_days") or 0),
            _procurement(row.get("procurement_type")),
        )
        for row in plant
    ]

    # ---------------------------------------------------------------- BOMs and alternates
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in r.rows(
        "bom_component",
        [
            "bom_id",
            "parent_item_id",
            "revision",
            "alternative",
            "priority",
            "base_quantity",
            "yield_pct",
            "status",
            "valid_from",
            "valid_to",
            "component_item_id",
            "quantity",
            "uom",
            "scrap_pct",
            "sequence",
        ],
    ):
        key = (
            str(row["bom_id"]),
            str(row["parent_item_id"]),
            str(row.get("revision") or "A"),
            str(row.get("alternative") or "1"),
        )
        groups[key].append(row)
    boms = []
    for (bom_id, parent, rev, alt), lines in groups.items():
        head = lines[0]
        status = str(head.get("status") or "released").lower()
        boms.append(
            Bom(
                bom_id,
                parent,
                rev,
                tuple(
                    BomLine(
                        str(ln["component_item_id"]),
                        _dec(ln["quantity"]) or ZERO,
                        str(ln.get("uom") or ""),
                        _dec(ln.get("scrap_pct")) or ZERO,
                        int(ln.get("sequence") or 10),
                    )
                    for ln in lines
                ),
                _dec(head.get("base_quantity")) or ONE,
                head.get("valid_from"),
                head.get("valid_to"),
                status if status in ("released", "draft", "obsolete") else "released",  # type: ignore[arg-type]
                _dec(head.get("yield_pct")) or Decimal(100),
                alt,
                int(head.get("priority") or 1),
            )
        )
    alternates = [
        AlternateRule(
            str(row["item_id"]),
            str(row["alternate_item_id"]),
            _dec(row.get("ratio")) or ONE,
            int(row.get("priority") or 1),
            bool(row.get("approved")),
            row.get("valid_from"),
            row.get("valid_to"),
            _dec(row.get("max_share_pct")),
            (str(row["customer_id"]),) if row.get("customer_id") else (),
            (),
            str(row.get("note") or ""),
        )
        for row in r.rows(
            "item_alternate",
            [
                "item_id",
                "alternate_item_id",
                "ratio",
                "priority",
                "approved",
                "valid_from",
                "valid_to",
                "max_share_pct",
                "customer_id",
                "note",
            ],
        )
    ]

    # ---------------------------------------------------------------- stock, supply, demand (warehouse-scoped)
    stock_fields = ["item_id", "warehouse_id", "lot_id", "stock_status", "quantity", "uom"]
    if r.mapping.has_ref("stock_balance", "lot.expiry_date"):
        stock_fields.append("lot.expiry_date")
    stock = []
    on_hand: dict[str, Decimal] = defaultdict(Decimal)
    for row in r.rows("stock_balance", stock_fields):
        qty = _dec(row.get("quantity")) or ZERO
        on_hand[str(row["item_id"])] += qty
        stock.append(
            StockLine(
                str(row["item_id"]),
                str(row["warehouse_id"]),
                qty,
                str(row.get("uom") or ""),
                str(row.get("stock_status") or "unrestricted"),
                row.get("lot_id"),
                row.get("lot.expiry_date"),
            )
        )
    po_fields = [
        "po_id",
        "line",
        "item_id",
        "supplier_id",
        "warehouse_id",
        "status",
        "quantity",
        "uom",
        "expected_date",
        "receipt_date",
        "open_quantity",
        "received_quantity",
        "rejected_quantity",
    ]
    if can_cost:
        po_fields += ["unit_price", "currency"]
    supply, deliveries, prices = [], [], []
    for row in r.rows("purchase_record", po_fields):
        status = str(row.get("status") or "").upper()
        ref = f"{row['po_id']}/{row.get('line') or ''}".rstrip("/")
        if status in ("OPEN", "PARTIAL", "ORDERED"):
            open_qty = row.get("open_quantity")
            qty = _dec(open_qty if open_qty is not None else row.get("quantity")) or ZERO
            due = row.get("expected_date")
            if due is None:
                r.issues.append(
                    Issue(
                        "missing_expected_date",
                        Severity.WARNING,
                        f"Open purchase line {ref} has no expected date; not used for planning.",
                        str(row["item_id"]),
                        ref,
                    )
                )
            elif qty:
                supply.append(
                    Supply(
                        ref,
                        str(row["item_id"]),
                        str(row["warehouse_id"]),
                        qty,
                        due,
                        str(row.get("uom") or ""),
                        "purchase",
                        row.get("supplier_id"),
                    )
                )
        elif status == "RECEIVED" and row.get("supplier_id") and row.get("expected_date"):
            received = _dec(row.get("received_quantity")) or _dec(row.get("quantity")) or ZERO
            deliveries.append(
                DeliveryRecord(
                    str(row["supplier_id"]),
                    str(row["item_id"]),
                    ref,
                    row["expected_date"],
                    row.get("receipt_date"),
                    _dec(row.get("quantity")) or ZERO,
                    received,
                    _dec(row.get("rejected_quantity")) or ZERO,
                )
            )
            if can_cost and row.get("unit_price") is not None and row.get("receipt_date"):
                prices.append(
                    PriceRecord(
                        str(row["supplier_id"]),
                        str(row["item_id"]),
                        row["receipt_date"],
                        _dec(row["unit_price"]) or ZERO,
                        str(row.get("currency") or ""),
                    )
                )
    demand = []
    order_fields = [
        "order_id",
        "line",
        "customer_id",
        "item_id",
        "warehouse_id",
        "quantity",
        "uom",
        "due_date",
        "priority",
        "order_date",
        "status",
        "ship_days",
    ]
    if can_cost:  # order value, margin and penalties are cost-sensitive (commitment protection needs cost:read)
        order_fields += ["unit_price", "currency", "margin_pct", "penalty_per_day"]
    for row in r.rows("customer_order_line", order_fields):
        if str(row.get("status") or "OPEN").upper() in CLOSED:
            continue
        demand.append(
            DemandLine(
                str(row["order_id"]),
                str(row.get("line") or "1"),
                str(row["item_id"]),
                str(row["warehouse_id"]),
                _dec(row.get("quantity")) or ZERO,
                row["due_date"],
                str(row.get("uom") or ""),
                str(row.get("customer_id") or ""),
                int(row.get("priority") or 5),
                row.get("order_date"),
                ship_days=int(row.get("ship_days") or 0),
                unit_price=_dec(row.get("unit_price")),
                currency=str(row.get("currency") or ""),
                margin_pct=_dec(row.get("margin_pct")),
                penalty_per_day=_dec(row.get("penalty_per_day")),
            )
        )

    # ---------------------------------------------------------------- suppliers and offers
    suppliers = {
        str(row["supplier_id"]): Supplier(
            str(row["supplier_id"]),
            str(row.get("name") or row["supplier_id"]),
            str(row.get("country") or ""),
            bool(row["approved"]) if row.get("approved") is not None else True,
            str(row.get("status") or "active"),
            (Certification(str(row["certification"]), row.get("certification_expiry")),)
            if row.get("certification")
            else (),
            str(row.get("currency") or ""),
            str(row.get("payment_terms") or ""),
        )
        for row in r.rows(
            "supplier",
            [
                "supplier_id",
                "name",
                "country",
                "approved",
                "status",
                "certification",
                "certification_expiry",
                "currency",
                "payment_terms",
            ],
        )
    }
    offers = []
    if can_cost:
        for row in r.rows(
            "supplier_item",
            [
                "supplier_id",
                "item_id",
                "price",
                "currency",
                "price_unit",
                "uom",
                "moq",
                "order_multiple",
                "lead_days",
                "valid_from",
                "valid_to",
                "approved",
                "freight_per_unit",
                "duty_pct",
                "capacity",
            ],
        ):
            offers.append(
                SupplierOffer(
                    str(row["supplier_id"]),
                    str(row["item_id"]),
                    _dec(row.get("price")) or ZERO,
                    str(row.get("currency") or ""),
                    _dec(row.get("price_unit")) or ONE,
                    str(row.get("uom") or ""),
                    _dec(row.get("moq")) or ZERO,
                    _dec(row.get("order_multiple")),
                    row.get("lead_days"),
                    row.get("valid_from"),
                    row.get("valid_to"),
                    bool(row["approved"]) if row.get("approved") is not None else True,
                    (),
                    _dec(row.get("capacity")),
                    _dec(row.get("freight_per_unit")),
                    _dec(row.get("duty_pct")),
                )
            )

    last_issue: dict[str, date | None] = {}
    for row in r.rows("inventory_transaction", ["item_id", "txn_type", "posting_date"]):
        if str(row.get("txn_type") or "").upper() in ("ISSUE", "TRANSFER_OUT") and row.get("posting_date"):
            iid = str(row["item_id"])
            seen = last_issue.get(iid)
            if seen is None or row["posting_date"] > seen:
                last_issue[iid] = row["posting_date"]

    data = PlanningData(
        today, items, tuple(boms), tuple(alternates), tuple(stock), (), tuple(supply), tuple(demand), tuple(policies)
    )
    available = {
        "demand": len(demand),
        "stock": len(stock),
        "boms": len(boms),
        "supply": len(supply),
        "lead_times": sum(1 for p in policies if p.lead_days is not None),
        "lot_rules": sum(1 for p in policies if p.min_lot or p.lot_size or p.multiple),
        "alternates": len(alternates),
        "offers": len(offers),
        "suppliers": len(suppliers),
        "deliveries": len(deliveries),
        "price_history": len(prices),
        "movements": len(last_issue),
        "item_attributes": len(items),
        "criticality": sum(1 for i in items.values() if i.critical),
        "calendar": 1,
    }
    return LoadedPlanning(
        data, suppliers, offers, deliveries, prices, last_issue, dict(on_hand), available, r.issues, can_cost
    )
