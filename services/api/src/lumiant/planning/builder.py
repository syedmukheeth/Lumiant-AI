"""Plain records (dicts from YAML scenario files or canonical query rows) → planning model objects."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from lumiant.planning.model import (
    AllocationPolicy,
    AlternateRule,
    Bom,
    BomLine,
    Calendar,
    Certification,
    DeliveryRecord,
    DemandLine,
    FxRate,
    Item,
    PlanningData,
    PlanningPolicy,
    PriceBreak,
    PriceRecord,
    Reservation,
    StockLine,
    Supplier,
    SupplierOffer,
    SupplierPolicy,
    Supply,
    UomConversion,
)
from lumiant.planning.transfers import TransferLane

Rec = dict[str, Any]


def dec(v: Any, default: Decimal | None = None) -> Decimal | None:
    if v is None or v == "":
        return default
    return Decimal(str(v))


def d(v: Any) -> Decimal:
    out = dec(v, Decimal(0))
    assert out is not None
    return out


def day(v: Any) -> date | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def item(r: Rec) -> Item:
    return Item(
        str(r.get("id") or r["item_id"]),
        str(r.get("description", "")),
        str(r.get("uom") or r.get("base_uom") or "EA"),
        str(r.get("group") or r.get("item_group") or ""),
        r.get("stage", ""),
        r.get("procurement", "buy"),
        bool(r.get("phantom", False)),
        r.get("status", "ACTIVE"),
        bool(r.get("critical", False)),
        r.get("lifecycle", "active"),
        r.get("superseded_by"),
        r.get("manufacturer", ""),
        r.get("mpn", ""),
        {k: str(v) for k, v in (r.get("attributes") or {}).items()},
    )


def boms(records: list[Rec]) -> tuple[Bom, ...]:
    out = []
    for r in records:
        lines = tuple(
            BomLine(
                str(ln["item"]),
                d(ln["qty"]),
                ln.get("uom", ""),
                d(ln.get("scrap_pct", 0)),
                int(ln.get("seq", (i + 1) * 10)),
            )
            for i, ln in enumerate(r["lines"])
        )
        out.append(
            Bom(
                str(r.get("id", f"BOM-{r['item']}-{r.get('rev', 'A')}")),
                str(r["item"]),
                str(r.get("rev", "A")),
                lines,
                d(r.get("base_qty", 1)),
                day(r.get("valid_from")),
                day(r.get("valid_to")),
                r.get("status", "released"),
                d(r.get("yield_pct", 100)),
                str(r.get("alternative", "1")),
                int(r.get("priority", 1)),
            )
        )
    return tuple(out)


def planning_data(raw: Rec) -> PlanningData:
    today = day(raw["today"])
    assert today is not None
    cal = raw.get("calendar") or {}
    alloc = raw.get("allocation") or {}
    return PlanningData(
        today=today,
        items={i.item_id: i for i in (item(r) for r in raw.get("items", []))},
        boms=boms(raw.get("boms", [])),
        alternates=tuple(
            AlternateRule(
                str(r["item"]),
                str(r["alternate"]),
                d(r.get("ratio", 1)),
                int(r.get("priority", 1)),
                bool(r.get("approved", True)),
                day(r.get("valid_from")),
                day(r.get("valid_to")),
                dec(r.get("max_share_pct")),
                tuple(r.get("customers_only", ())),
                tuple(r.get("customers_excluded", ())),
            )
            for r in raw.get("alternates", [])
        ),
        stock=tuple(
            StockLine(
                str(r["item"]),
                str(r.get("wh", "W1")),
                d(r["qty"]),
                r.get("uom", ""),
                r.get("status", "unrestricted"),
                r.get("lot"),
                day(r.get("expiry")),
                r.get("owner", "company"),
            )
            for r in raw.get("stock", [])
        ),
        reservations=tuple(
            Reservation(str(r["item"]), str(r.get("wh", "W1")), d(r["qty"]), r.get("ref", ""))
            for r in raw.get("reservations", [])
        ),
        supply=tuple(
            Supply(
                str(r["ref"]),
                str(r["item"]),
                str(r.get("wh", "W1")),
                d(r["qty"]),
                day(r["due"]) or today,
                r.get("uom", ""),
                r.get("kind", "purchase"),
                r.get("supplier"),
            )
            for r in raw.get("supply", [])
        ),
        demand=tuple(
            DemandLine(
                str(r["order"]),
                str(r.get("line", 1)),
                str(r["item"]),
                str(r.get("wh", "W1")),
                d(r["qty"]),
                day(r["due"]) or today,
                r.get("uom", ""),
                str(r.get("customer", "")),
                int(r.get("priority", 5)),
                day(r.get("order_date")),
                r.get("kind", "customer_order"),
                int(r.get("ship_days", 0)),
                dec(r.get("unit_price")),
                r.get("currency", ""),
                dec(r.get("margin_pct")),
                dec(r.get("penalty_per_day")),
                bool(r.get("confirmed", True)),
            )
            for r in raw.get("demand", [])
        ),
        policies=tuple(
            PlanningPolicy(
                str(r["item"]),
                r.get("wh"),
                r.get("lot_rule", "lot_for_lot"),
                dec(r.get("lot_size")),
                dec(r.get("min_lot")),
                dec(r.get("multiple")),
                d(r.get("safety_stock", 0)),
                r.get("lead_days"),
                int(r.get("receiving_days", 0)),
                int(r.get("inspection_days", 0)),
            )
            for r in raw.get("policies", [])
        ),
        conversions=tuple(
            UomConversion(r["from"], r["to"], d(r["factor"]), r.get("item")) for r in raw.get("conversions", [])
        ),
        calendar=Calendar(
            frozenset(cal.get("weekend", [4, 5])), frozenset(x for x in (day(h) for h in cal.get("holidays", [])) if x)
        ),
        allocation=AllocationPolicy(
            tuple(alloc.get("keys", ("due", "priority", "order_date"))), bool(alloc.get("protect_safety_stock", True))
        ),
    )


def suppliers(records: list[Rec]) -> dict[str, Supplier]:
    return {
        str(r["id"]): Supplier(
            str(r["id"]),
            r.get("name", str(r["id"])),
            r.get("country", ""),
            bool(r.get("approved", True)),
            r.get("status", "active"),
            tuple(
                Certification(c["name"], day(c.get("expires")), bool(c.get("mandatory", True)))
                for c in r.get("certifications", [])
            ),
            r.get("currency", ""),
            r.get("payment_terms", ""),
            r.get("risk", ""),
        )
        for r in records
    }


def offers(records: list[Rec]) -> list[SupplierOffer]:
    return [
        SupplierOffer(
            str(r["supplier"]),
            str(r["item"]),
            d(r["price"]),
            r.get("currency", "SAR"),
            d(r.get("price_unit", 1)),
            r.get("uom", ""),
            d(r.get("moq", 0)),
            dec(r.get("multiple")),
            r.get("lead_days"),
            day(r.get("valid_from")),
            day(r.get("valid_to")),
            bool(r.get("approved", True)),
            tuple(PriceBreak(d(b["min"]), d(b["price"])) for b in r.get("breaks", [])),
            dec(r.get("capacity")),
            dec(r.get("freight")),
            dec(r.get("duty_pct")),
            dec(r.get("other")),
            r.get("ref", ""),
        )
        for r in records
    ]


def deliveries(records: list[Rec]) -> list[DeliveryRecord]:
    return [
        DeliveryRecord(
            str(r["supplier"]),
            str(r["item"]),
            str(r.get("ref", "")),
            day(r["promised"]) or date.min,
            day(r.get("received")),
            d(r.get("ordered", r.get("received_qty", 0))),
            d(r.get("received_qty", 0)),
            d(r.get("rejected", 0)),
        )
        for r in records
    ]


def prices(records: list[Rec]) -> list[PriceRecord]:
    return [
        PriceRecord(
            str(r["supplier"]),
            str(r["item"]),
            day(r["day"]) or date.min,
            d(r["price"]),
            r.get("currency", "SAR"),
            r.get("kind", "purchase"),
        )
        for r in records
    ]


def fx(records: list[Rec]) -> list[FxRate]:
    return [FxRate(r["from"], r["to"], d(r["rate"]), day(r["valid_from"]) or date.min) for r in records]


def supplier_policy(r: Rec | None) -> SupplierPolicy:
    if not r:
        return SupplierPolicy()
    weights = {k: d(v) for k, v in (r.get("weights") or {}).items()} or SupplierPolicy().weights
    return SupplierPolicy(
        str(r.get("name") or r.get("mode") or "balanced"),
        r.get("mode", "weighted"),
        weights,
        dec(r.get("max_rejection_pct")),
        dec(r.get("min_on_time_pct")),
        int(r.get("min_evidence_lots", 3)),
        bool(r.get("require_certifications", True)),
        r.get("base_currency", "SAR"),
        bool(r.get("require_need_date", True)),
    )


def lanes(records: list[Rec]) -> list[TransferLane]:
    return [
        TransferLane(
            str(r["from"]),
            str(r["to"]),
            int(r["lead_days"]),
            dec(r.get("cost")),
            bool(r.get("allowed", True)),
            r.get("note", ""),
        )
        for r in records
    ]
