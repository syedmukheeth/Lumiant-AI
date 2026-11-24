"""SYNTHETIC manufacturing and distribution company for the planning engine (`demo-delta`).

"Demo Delta Industrial" is fictional: a pump and valve maker with a Riyadh plant, a Dammam plant and a Jeddah
distribution centre. Every record is hand-authored and dated relative to `as_of`, so planning outcomes are known
in advance and identical on every run (no randomness). Planted situations (see `SCENARIOS`):

* competing customer orders for a pump whose impeller is short and whose preferred supplier is slow (combined A, B);
* a multi-level skid (pump + motor subassembly) and a phantom fastener kit (scenarios 22, 28);
* a BOM revision that replaces a steel grade 60 days ahead (scenario 24, combined F);
* an approved seal alternate and an unapproved impeller look-alike (scenarios 26, 45);
* three impeller suppliers - cheap but poor quality, balanced, fast but expensive - one supplier with an expired
  certificate, one unapproved, one quoting in USD (combined C, scenarios 56, 58, 60);
* stock that is blocked, in inspection, returned or expired (scenarios 10, 11);
* surplus in Dammam and a shortage in Jeddah (combined D);
* duplicate bolt codes used in different BOMs (combined E), a critical spare and an ordinary dormant gasket
  (combined K).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from lumiant.synthetic.generator import SyntheticDataset

Record = dict[str, object]
TENANT = "demo-delta"
D = Decimal


def build(as_of: date) -> SyntheticDataset:
    def day(n: int) -> date:
        return as_of + timedelta(days=n)

    departments: list[Record] = [
        {"department_id": "MFG", "name": "Manufacturing"},
        {"department_id": "DIST", "name": "Distribution"},
    ]
    warehouses = [
        {
            "warehouse_id": "RYD1",
            "name": "Riyadh Plant",
            "department_id": "MFG",
            "site": "Riyadh",
            "temperature_controlled": False,
            "flammable_storage": True,
        },
        {
            "warehouse_id": "DMM1",
            "name": "Dammam Plant",
            "department_id": "MFG",
            "site": "Dammam",
            "temperature_controlled": False,
            "flammable_storage": False,
        },
        {
            "warehouse_id": "JED1",
            "name": "Jeddah Distribution Centre",
            "department_id": "DIST",
            "site": "Jeddah",
            "temperature_controlled": True,
            "flammable_storage": False,
        },
    ]
    locations: list[Record] = [
        {"location_id": loc, "warehouse_id": wh, "name": name}
        for wh, loc, name in (
            ("RYD1", "RM", "Raw materials"),
            ("RYD1", "FG", "Finished goods"),
            ("RYD1", "QI", "Quality inspection"),
            ("DMM1", "RM", "Raw materials"),
            ("JED1", "FG", "Finished goods"),
        )
    ]

    def it(item_id: str, desc: str, group: str, stage: str, uom: str = "EA", **kw: object) -> Record:
        return {
            "item_id": item_id,
            "item_code": item_id,
            "description": desc,
            "item_group": group,
            "inventory_stage": stage,
            "abc_class": kw.get("abc", "B"),
            "base_uom": uom,
            "status": kw.get("status", "ACTIVE"),
            "lot_tracked": kw.get("lot", False),
            "shelf_life_days": kw.get("shelf"),
            "storage_temp_min": None,
            "storage_temp_max": None,
            "flammability_class": None,
            "default_supplier_id": kw.get("supplier"),
            "manufacturer": kw.get("manufacturer"),
            "mpn": kw.get("mpn"),
            "lifecycle_status": kw.get("lifecycle", "active"),
            "superseded_by": kw.get("superseded_by"),
            "critical": kw.get("critical", False),
        }

    items = [
        it("FG-PUMP-100", "Centrifugal pump 100 m3/h", "PUMPS", "FINISHED", abc="A"),
        it("FG-VALVE-50", "Gate valve DN50 PN16", "VALVES", "FINISHED", abc="A"),
        it("FG-SKID-1", "Pump skid with motor", "PUMPS", "FINISHED", abc="A"),
        it("SA-MOTOR-15", "Motor assembly 15 kW", "MOTORS", "SEMI"),
        it("PH-KIT-01", "Fastener kit (phantom)", "KITS", "SEMI"),
        it("RM-CASING", "Pump casing ductile iron", "CASTINGS", "RAW", supplier="SUP-IRON"),
        it("RM-IMPELLER", "Impeller 250 mm bronze", "CASTINGS", "RAW", supplier="SUP-ALPHA"),
        it("RM-IMPELLER-X", "Impeller 250 mm bronze (unqualified source)", "CASTINGS", "RAW"),
        it("RM-SHAFT", "Shaft 40 mm stainless", "MACHINED", "RAW"),
        it("RM-SEAL", "Mechanical seal 40 mm", "SEALS", "RAW", lot=True, shelf=720),
        it("RM-SEAL-ALT", "Mechanical seal 40 mm (approved equivalent)", "SEALS", "RAW", lot=True, shelf=720),
        it("RM-BOLT-M10", "Bolt M10x50 SS", "FASTENERS", "RAW", abc="C"),
        it("RM-BOLT-M10B", "BOLT M10 X 50 S/S", "FASTENERS", "RAW", abc="C"),
        it(
            "RM-STEEL-S1",
            "Steel plate S275 10 mm",
            "STEEL",
            "RAW",
            "KG",
            lifecycle="superseded",
            superseded_by="RM-STEEL-S2",
        ),
        it("RM-STEEL-S2", "Steel plate S355 10 mm", "STEEL", "RAW", "KG"),
        it("RM-COPPER", "Copper winding wire 1.5 mm", "ELECTRICAL", "RAW", "KG"),
        it(
            "SP-BEARING-7310",
            "Angular bearing 7310 for main compressor",
            "SPARES",
            "SPARE",
            abc="C",
            critical=True,
            manufacturer="Fictional Bearings",
            mpn="FB-7310-BE",
        ),
        it("SP-GASKET-OLD", "Gasket 300 mm graphite", "SPARES", "SPARE", abc="C"),
        it("FG-VALVE-80", "Gate valve DN80 PN16", "VALVES", "FINISHED"),
    ]

    def iw(item_id: str, wh: str, proc: str, lead: int | None, price: str, **kw: object) -> Record:
        return {
            "item_id": item_id,
            "warehouse_id": wh,
            "abc_class": None,
            "planning_type": "mrp",
            "price_control": "moving_average",
            "valuation_price": D(price),
            "currency": "SAR",
            "procurement_type": proc,
            "phantom": kw.get("phantom", False),
            "lead_days": lead,
            "receiving_days": kw.get("receiving", 1),
            "inspection_days": kw.get("inspection", 0),
            "safety_stock": D(str(kw.get("safety", "0"))),
            "lot_rule": kw.get("lot_rule", "lot_for_lot"),
            "lot_size": None,
            "min_lot": D(str(kw["min_lot"])) if "min_lot" in kw else None,
            "lot_multiple": D(str(kw["multiple"])) if "multiple" in kw else None,
        }

    item_wh = [
        iw("FG-PUMP-100", "RYD1", "make", 4, "5200"),
        iw("FG-VALVE-50", "RYD1", "make", 3, "900"),
        iw("FG-SKID-1", "RYD1", "make", 6, "14800"),
        iw("SA-MOTOR-15", "RYD1", "make", 5, "6100"),
        iw("PH-KIT-01", "RYD1", "make", 0, "40", phantom=True),
        iw("RM-CASING", "RYD1", "buy", 15, "1100", inspection=1),
        iw("RM-IMPELLER", "RYD1", "buy", 20, "850", inspection=1),
        iw("RM-IMPELLER-X", "RYD1", "buy", 10, "700"),
        iw("RM-SHAFT", "RYD1", "buy", 12, "320"),
        iw("RM-SEAL", "RYD1", "buy", 10, "410", safety="10"),
        iw("RM-SEAL-ALT", "RYD1", "buy", 10, "430"),
        iw("RM-BOLT-M10", "RYD1", "buy", 5, "2.5", min_lot=500, multiple=100),
        iw("RM-BOLT-M10B", "RYD1", "buy", 5, "2.4", min_lot=500, multiple=100),
        iw("RM-STEEL-S1", "RYD1", "buy", 25, "4.1"),
        iw("RM-STEEL-S2", "RYD1", "buy", 25, "4.6"),
        iw("RM-COPPER", "RYD1", "buy", None, "38"),  # lead time not maintained (scenario 80)
        iw("SP-BEARING-7310", "RYD1", "buy", 40, "2300"),
        iw("SP-GASKET-OLD", "RYD1", "buy", 15, "95"),
        iw("FG-VALVE-50", "DMM1", "make", 3, "900"),
        iw("FG-VALVE-50", "JED1", "buy", 12, "920"),
        iw("FG-PUMP-100", "JED1", "buy", 18, "5300"),
    ]

    def sb(
        item_id: str,
        wh: str,
        loc: str,
        qty: str,
        uom: str = "EA",
        status: str = "unrestricted",
        lot: str | None = None,
        price: str = "0",
    ) -> Record:
        return {
            "item_id": item_id,
            "warehouse_id": wh,
            "location_id": loc,
            "lot_id": lot,
            "quantity": D(qty),
            "uom": uom,
            "valuation_price": D(price),
            "currency": "SAR",
            "stock_status": status,
        }

    stock = [
        sb("FG-PUMP-100", "RYD1", "FG", "12", price="5200"),
        sb("FG-PUMP-100", "RYD1", "QI", "3", status="quality_inspection", price="5200"),
        sb("FG-PUMP-100", "RYD1", "FG", "2", status="returns", price="5200"),
        sb("FG-VALVE-50", "RYD1", "FG", "40", price="900"),
        sb("FG-VALVE-50", "DMM1", "RM", "160", price="900"),
        sb("FG-VALVE-50", "JED1", "FG", "5", price="920"),
        sb("RM-CASING", "RYD1", "RM", "30", price="1100"),
        sb("RM-IMPELLER", "RYD1", "RM", "10", price="850"),
        sb("RM-IMPELLER", "RYD1", "QI", "4", status="blocked", price="850"),
        sb("RM-IMPELLER-X", "RYD1", "RM", "25", price="700"),
        sb("RM-SHAFT", "RYD1", "RM", "60", price="320"),
        sb("RM-SEAL", "RYD1", "RM", "30", lot="L-SEAL-01", price="410"),
        sb("RM-SEAL", "RYD1", "RM", "8", lot="L-SEAL-00", price="410"),
        sb("RM-SEAL-ALT", "RYD1", "RM", "20", lot="L-SALT-01", price="430"),
        sb("RM-BOLT-M10", "RYD1", "RM", "300", price="2.5"),
        sb("RM-BOLT-M10B", "RYD1", "RM", "450", price="2.4"),
        sb("RM-STEEL-S1", "RYD1", "RM", "900", "KG", price="4.1"),
        sb("RM-COPPER", "RYD1", "RM", "10", "KG", price="38"),
        sb("SP-BEARING-7310", "RYD1", "RM", "2", price="2300"),
        sb("SP-GASKET-OLD", "RYD1", "RM", "35", price="95"),
    ]

    lots = [
        {
            "lot_id": "L-SEAL-01",
            "item_id": "RM-SEAL",
            "warehouse_id": "RYD1",
            "receipt_date": day(-60),
            "expiry_date": day(400),
            "supplier_id": "SUP-SEALS",
            "unit_cost": D("410"),
            "currency": "SAR",
        },
        {
            "lot_id": "L-SEAL-00",
            "item_id": "RM-SEAL",
            "warehouse_id": "RYD1",
            "receipt_date": day(-700),
            "expiry_date": day(-5),
            "supplier_id": "SUP-SEALS",
            "unit_cost": D("400"),
            "currency": "SAR",
        },
        {
            "lot_id": "L-SALT-01",
            "item_id": "RM-SEAL-ALT",
            "warehouse_id": "RYD1",
            "receipt_date": day(-30),
            "expiry_date": day(500),
            "supplier_id": "SUP-SEALS",
            "unit_cost": D("430"),
            "currency": "SAR",
        },
    ]

    def bom(bom_id: str, parent: str, rev: str, lines: list[tuple[str, str, str]], **kw: object) -> list[Record]:
        return [
            {
                "bom_id": bom_id,
                "parent_item_id": parent,
                "revision": rev,
                "alternative": "1",
                "priority": 1,
                "base_quantity": D("1"),
                "yield_pct": D(str(kw.get("yield_pct", "100"))),
                "status": "released",
                "valid_from": kw.get("valid_from"),
                "valid_to": kw.get("valid_to"),
                "component_item_id": comp,
                "quantity": D(qty),
                "uom": uom,
                "scrap_pct": D(str(kw.get("scrap", "0"))) if comp == kw.get("scrap_item") else D("0"),
                "sequence": (i + 1) * 10,
            }
            for i, (comp, qty, uom) in enumerate(lines)
        ]

    pump_lines = [
        ("RM-CASING", "1", "EA"),
        ("RM-IMPELLER", "1", "EA"),
        ("RM-SHAFT", "1", "EA"),
        ("RM-SEAL", "2", "EA"),
        ("PH-KIT-01", "1", "EA"),
    ]
    boms = [
        *bom("BOM-PUMP", "FG-PUMP-100", "A", [*pump_lines, ("RM-STEEL-S1", "12", "KG")], valid_to=day(60)),
        *bom("BOM-PUMP", "FG-PUMP-100", "B", [*pump_lines, ("RM-STEEL-S2", "12", "KG")], valid_from=day(60)),
        *bom("BOM-KIT", "PH-KIT-01", "A", [("RM-BOLT-M10", "8", "EA")]),
        *bom(
            "BOM-VALVE",
            "FG-VALVE-50",
            "A",
            [("RM-CASING", "1", "EA"), ("RM-SEAL", "1", "EA"), ("RM-BOLT-M10B", "4", "EA")],
        ),
        *bom("BOM-SKID", "FG-SKID-1", "A", [("FG-PUMP-100", "1", "EA"), ("SA-MOTOR-15", "1", "EA")]),
        *bom("BOM-MOTOR", "SA-MOTOR-15", "A", [("RM-COPPER", "6", "KG"), ("RM-SHAFT", "1", "EA")], yield_pct="98"),
    ]

    alternates = [
        {
            "item_id": "RM-SEAL",
            "alternate_item_id": "RM-SEAL-ALT",
            "ratio": D("1"),
            "priority": 1,
            "approved": True,
            "valid_from": day(-365),
            "valid_to": None,
            "max_share_pct": None,
            "customer_id": None,
            "note": "Same dimensions and rating; engineering approval ENG-2041",
        },
        {
            "item_id": "RM-IMPELLER",
            "alternate_item_id": "RM-IMPELLER-X",
            "ratio": D("1"),
            "priority": 1,
            "approved": False,
            "valid_from": None,
            "valid_to": None,
            "max_share_pct": None,
            "customer_id": None,
            "note": "Look-alike from an unqualified foundry; not approved",
        },
    ]

    suppliers = [
        {
            "supplier_id": "SUP-ALPHA",
            "name": "Alpha Foundry (fictional)",
            "country": "SA",
            "approved": True,
            "status": "active",
            "certification": "ISO 9001",
            "certification_expiry": day(300),
            "currency": "SAR",
            "payment_terms": "60 days",
        },
        {
            "supplier_id": "SUP-BETA",
            "name": "Beta Castings (fictional)",
            "country": "SA",
            "approved": True,
            "status": "active",
            "certification": "ISO 9001",
            "certification_expiry": day(200),
            "currency": "SAR",
            "payment_terms": "45 days",
        },
        {
            "supplier_id": "SUP-GAMMA",
            "name": "Gamma Express Metals (fictional)",
            "country": "AE",
            "approved": True,
            "status": "active",
            "certification": "ISO 9001",
            "certification_expiry": day(150),
            "currency": "USD",
            "payment_terms": "30 days",
        },
        {
            "supplier_id": "SUP-OMEGA",
            "name": "Omega Trading (fictional)",
            "country": "SA",
            "approved": True,
            "status": "active",
            "certification": "ISO 9001",
            "certification_expiry": day(-20),
            "currency": "SAR",
            "payment_terms": "30 days",
        },
        {
            "supplier_id": "SUP-ZETA",
            "name": "Zeta General Supply (fictional)",
            "country": "SA",
            "approved": False,
            "status": "active",
            "certification": None,
            "certification_expiry": None,
            "currency": "SAR",
            "payment_terms": "cash",
        },
        {
            "supplier_id": "SUP-IRON",
            "name": "Iron Works (fictional)",
            "country": "SA",
            "approved": True,
            "status": "active",
            "certification": "ISO 9001",
            "certification_expiry": day(400),
            "currency": "SAR",
            "payment_terms": "60 days",
        },
        {
            "supplier_id": "SUP-SEALS",
            "name": "Seal Systems (fictional)",
            "country": "SA",
            "approved": True,
            "status": "active",
            "certification": "ISO 9001",
            "certification_expiry": day(400),
            "currency": "SAR",
            "payment_terms": "60 days",
        },
    ]

    def offer(sup: str, item_id: str, price: str, lead: int | None, **kw: object) -> Record:
        return {
            "supplier_id": sup,
            "item_id": item_id,
            "supplier_item_code": f"{sup[-4:]}-{item_id[-6:]}",
            "price": D(price),
            "currency": kw.get("currency", "SAR"),
            "price_unit": D("1"),
            "uom": "EA",
            "moq": D(str(kw.get("moq", "0"))),
            "order_multiple": None,
            "lead_days": lead,
            "valid_from": day(-90),
            "valid_to": day(kw.get("valid_days", 90)),  # type: ignore[arg-type]
            "approved": kw.get("approved", True),
            "freight_per_unit": D(str(kw["freight"])) if "freight" in kw else None,
            "duty_pct": D(str(kw["duty"])) if "duty" in kw else None,
            "capacity": D(str(kw["capacity"])) if "capacity" in kw else None,
        }

    supplier_items = [
        offer("SUP-ALPHA", "RM-IMPELLER", "820", 20, freight="0", duty="0"),
        offer("SUP-BETA", "RM-IMPELLER", "890", 10, freight="0", duty="0"),
        offer("SUP-GAMMA", "RM-IMPELLER", "260", 4, currency="USD", freight="8", duty="5"),
        offer("SUP-OMEGA", "RM-IMPELLER", "800", 8, freight="0", duty="0"),
        offer("SUP-ZETA", "RM-IMPELLER", "600", 5),
        offer("SUP-IRON", "RM-CASING", "1080", 15, freight="0", duty="0"),
        offer("SUP-SEALS", "RM-SEAL", "405", 10, freight="0", duty="0"),
        offer("SUP-SEALS", "RM-SEAL-ALT", "425", 10, freight="0", duty="0"),
        offer("SUP-IRON", "RM-STEEL-S2", "4.6", 25, moq="2000"),
    ]

    purchases: list[Record] = []

    def po(
        po_id: str,
        sup: str,
        item_id: str,
        qty: str,
        price: str,
        promised: int,
        received: int | None,
        rejected: str = "0",
        wh: str = "RYD1",
        uom: str = "EA",
    ) -> None:
        q = D(qty)
        rec = D(qty) if received is not None else D("0")
        purchases.append(
            {
                "po_id": po_id,
                "line": "10",
                "item_id": item_id,
                "supplier_id": sup,
                "warehouse_id": wh,
                "order_date": day(promised - 25),
                "receipt_date": day(received) if received is not None else None,
                "quantity": q,
                "uom": uom,
                "unit_price": D(price),
                "currency": "SAR",
                "status": "RECEIVED" if received is not None else "OPEN",
                "expected_date": day(promised),
                "open_quantity": D("0") if received is not None else q,
                "received_quantity": rec,
                "rejected_quantity": D(rejected),
            }
        )

    # Delivery history: Alpha cheap but 12% rejected; Beta reliable; Gamma fast, one late; Omega no recent history.
    for n, m in enumerate((-300, -240, -180, -120)):
        po(f"PO-A{n}", "SUP-ALPHA", "RM-IMPELLER", "50", "800", m, m, "6")
        po(f"PO-B{n}", "SUP-BETA", "RM-IMPELLER", "50", "860", m, m - 1, "0")
        po(f"PO-G{n}", "SUP-GAMMA", "RM-IMPELLER", "20", "970", m, m + (6 if n == 2 else 0), "0")
    po("PO-O0", "SUP-OMEGA", "RM-IMPELLER", "10", "780", -400, -400, "0")
    po("PO-S0", "SUP-SEALS", "RM-SEAL", "100", "400", -60, -60, "1")
    po("PO-OPEN-CAS", "SUP-IRON", "RM-CASING", "20", "1080", 9, None)  # open: arrives in 9 days
    po("PO-OPEN-SFT", "SUP-IRON", "RM-SHAFT", "40", "320", 30, None)

    def so(
        order_id: str, line: str, customer: str, item_id: str, wh: str, qty: str, due: int, prio: int, ordered: int
    ) -> Record:
        return {
            "order_id": order_id,
            "line": line,
            "customer_id": customer,
            "item_id": item_id,
            "warehouse_id": wh,
            "quantity": D(qty),
            "uom": "EA",
            "due_date": day(due),
            "priority": prio,
            "order_date": day(ordered),
            "status": "OPEN",
            # Commercial terms for customer commitment protection (fictional): selling price, margin, penalty.
            "ship_days": 1 if wh == "JED1" else 2,
            "unit_price": price_of[item_id],
            "currency": "SAR",
            "margin_pct": margin_of[item_id],
            "penalty_per_day": (price_of[item_id] * D(qty) * D("0.005")).quantize(D("0.01")) if prio <= 2 else None,
        }

    price_of = {"FG-PUMP-100": D("18500"), "FG-VALVE-50": D("2900"), "FG-SKID-1": D("52000")}
    margin_of = {"FG-PUMP-100": D("22"), "FG-VALVE-50": D("18"), "FG-SKID-1": D("25")}
    orders = [
        so(
            "SO-1001", "10", "CUST-OASIS", "FG-PUMP-100", "RYD1", "30", 28, 1, -5
        ),  # key customer: protectable with a faster supplier
        so("SO-1002", "10", "CUST-HARBOR", "FG-PUMP-100", "RYD1", "15", 35, 3, -10),
        so("SO-1003", "10", "CUST-DUNE-WATER", "FG-VALVE-50", "RYD1", "60", 14, 2, -3),
        so("SO-1004", "10", "CUST-OASIS", "FG-SKID-1", "RYD1", "4", 45, 2, -1),
        so("SO-1005", "10", "CUST-RETAIL", "FG-VALVE-50", "JED1", "80", 10, 4, -2),  # Jeddah short; Dammam has surplus
        so("SO-1006", "10", "CUST-DUNE-WATER", "FG-PUMP-100", "RYD1", "5", 90, 5, 0),  # after the revision change
    ]

    reorder = [
        {
            "item_id": "RM-SEAL",
            "warehouse_id": "RYD1",
            "min_stock": D("10"),
            "max_stock": D("80"),
            "reorder_level": D("20"),
        },
        {
            "item_id": "RM-BOLT-M10",
            "warehouse_id": "RYD1",
            "min_stock": D("200"),
            "max_stock": D("2000"),
            "reorder_level": D("400"),
        },
    ]

    def mv(txn: str, kind: str, item_id: str, qty: str, n: int, wh: str = "RYD1", uom: str = "EA") -> Record:
        return {
            "txn_id": txn,
            "txn_type": kind,
            "item_id": item_id,
            "warehouse_id": wh,
            "location_id": "RM",
            "lot_id": None,
            "quantity": D(qty),
            "uom": uom,
            "unit_cost": None,
            "currency": "SAR",
            "posting_date": day(n),
        }

    movements = [
        mv("MV-1", "ISSUE", "RM-CASING", "-10", -20),
        mv("MV-2", "ISSUE", "RM-IMPELLER", "-8", -15),
        mv("MV-3", "ISSUE", "RM-SEAL", "-12", -12),
        mv("MV-4", "ISSUE", "RM-BOLT-M10", "-80", -9),
        mv("MV-5", "ISSUE", "RM-BOLT-M10B", "-40", -30),
        mv("MV-6", "ISSUE", "SP-BEARING-7310", "-1", -800),
        mv("MV-7", "ISSUE", "SP-GASKET-OLD", "-2", -700),
        mv("MV-8", "ISSUE", "RM-STEEL-S1", "-120", -10, uom="KG"),
        mv("MV-9", "ISSUE", "FG-VALVE-50", "-20", -5),
        mv("MV-10", "ISSUE", "RM-SHAFT", "-6", -18),
        mv("MV-11", "ISSUE", "FG-PUMP-100", "-4", -7),
        mv("MV-12", "ISSUE", "RM-COPPER", "-12", -25, uom="KG"),
    ]

    tables: dict[str, list[Record]] = {
        "department": departments,
        "warehouse": warehouses,
        "storage_location": locations,
        "supplier": suppliers,
        "item": items,
        "item_warehouse": item_wh,
        "stock_balance": stock,
        "lot": lots,
        "reorder_policy": reorder,
        "inventory_transaction": movements,
        "purchase_record": purchases,
        "bom_component": boms,
        "item_alternate": alternates,
        "supplier_item": supplier_items,
        "customer_order_line": orders,
    }
    scenarios = {
        "competing_orders_short_component": [["FG-PUMP-100", "RM-IMPELLER"]],
        "phantom_and_multilevel": [["FG-SKID-1", "PH-KIT-01", "SA-MOTOR-15"]],
        "bom_revision_change": [["FG-PUMP-100", "RM-STEEL-S1", "RM-STEEL-S2"]],
        "approved_and_unapproved_alternates": [["RM-SEAL", "RM-SEAL-ALT"], ["RM-IMPELLER", "RM-IMPELLER-X"]],
        "supplier_policies": [["RM-IMPELLER", "SUP-ALPHA", "SUP-BETA", "SUP-GAMMA", "SUP-OMEGA", "SUP-ZETA"]],
        "warehouse_balancing": [["FG-VALVE-50", "DMM1", "JED1"]],
        "duplicate_items": [["RM-BOLT-M10", "RM-BOLT-M10B"]],
        "critical_spare_vs_dormant": [["SP-BEARING-7310", "SP-GASKET-OLD"]],
        "missing_lead_time": [["RM-COPPER"]],
    }
    return SyntheticDataset(TENANT, 0, as_of, tables, scenarios)
