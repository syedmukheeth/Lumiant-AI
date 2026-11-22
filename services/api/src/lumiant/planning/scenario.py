"""Scenario orchestration (docs/UNIVERSAL_SCENARIO_ENGINE_ARCHITECTURE.md).

A business question or event is mapped to *capabilities* (reusable calculations), each with the data it needs.
`assess` reports the known facts, the missing data, the capabilities that are not built yet, the clarifying
questions to ask, and whether only a clearly labelled preliminary analysis is possible. A combination of scenarios
is simply several capabilities over the same planning data: nothing is hard-coded per example. Requests that touch
an unsupported capability are returned as `capability_gaps` so they can be recorded as candidate new rules instead
of being answered as if they were solved.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from lumiant.agent.terminology import normalize

Status = Literal["implemented", "partial", "planned"]


@dataclass(frozen=True)
class Capability:
    name: str
    title: str
    status: Status
    requires: tuple[str, ...]  # data keys (see DATA_KEYS)
    optional: tuple[str, ...] = ()
    triggers: tuple[str, ...] = ()  # regex fragments on the normalised question
    scenarios: tuple[int, ...] = ()
    limitation: str = ""


DATA_KEYS = {
    "demand": "customer orders or forecast (item, quantity, due date, warehouse)",
    "stock": "on-hand stock with stock status",
    "boms": "released bills of materials with revisions and effective dates",
    "supply": "open purchase / production orders with expected dates",
    "lead_times": "production and supplier lead times per item",
    "lot_rules": "lot-sizing rules, MOQ and order multiples",
    "alternates": "approved alternate-item relationships",
    "offers": "supplier–item prices, MOQ, lead times and approval",
    "suppliers": "supplier master with approval and certificates",
    "deliveries": "supplier delivery and inspection history",
    "price_history": "historical purchase prices",
    "fx": "approved exchange rates with effective dates",
    "charges": "freight, duty and other landed-cost charges",
    "lanes": "allowed warehouse transfer lanes with lead time and cost",
    "movements": "inventory movement history",
    "criticality": "spare-part criticality / equipment links",
    "work_centres": "work centres, capacities and shift calendars",
    "routings": "routings with operation times",
    "calendar": "working calendar and holidays",
    "item_attributes": "item specifications and manufacturer part numbers",
}

CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "order_fulfilment",
        "Order fulfilment and promise dates",
        "implemented",
        ("demand", "stock"),
        ("supply", "boms", "lead_times", "alternates", "calendar"),
        (
            r"fulfil|fulfill|deliver (on time|by)|can we (ship|supply|meet)|orders? (at risk|due)|"
            r"backorder|partial deliver",
            r"تلبيه|تسليم",
        ),
        (1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 14),
    ),
    Capability(
        "material_requirements",
        "Time-phased material requirements (MRP)",
        "implemented",
        ("demand", "stock", "boms"),
        ("supply", "lead_times", "lot_rules", "alternates", "calendar"),
        (
            r"raw materials?|material requirement|\bmrp\b|components? (required|needed)|"
            r"what (should|do) we (buy|purchase|manufacture|make)",
            r"what is missing|shortage",
        ),
        (21, 22, 23, 24, 25, 27, 28, 61, 62, 63),
    ),
    Capability(
        "bom_explosion",
        "BOM explosion",
        "implemented",
        ("boms",),
        (),
        (r"\bbom\b|bill of materials?|explode|every component",),
        (21, 22, 24, 25, 27, 28),
    ),
    Capability(
        "substitution",
        "Approved alternate items",
        "implemented",
        ("alternates", "stock"),
        ("demand",),
        (r"substitut|alternat(e|ive) (item|material|component)|replacement part",),
        (26, 42, 43, 44, 45),
    ),
    Capability(
        "supplier_comparison",
        "Supplier comparison before a PO",
        "implemented",
        ("offers", "suppliers"),
        ("deliveries", "price_history", "fx", "charges", "lead_times"),
        (r"supplier|vendor|quotation|quote|\bpo\b|purchase order|best (price|value)|landed cost",),
        tuple(range(46, 61)),
    ),
    Capability(
        "price_check",
        "Quotation vs historical price",
        "implemented",
        ("offers", "price_history"),
        ("fx",),
        (r"historical price|price (increase|variance)|higher than (last|before)",),
        (50, 66),
    ),
    Capability(
        "transfer_balancing",
        "Warehouse balancing and transfers",
        "implemented",
        ("stock", "lanes"),
        ("demand",),
        (r"transfer|surplus|rebalanc|other warehouse",),
        (12, 13),
    ),
    Capability(
        "duplicates",
        "Duplicate item detection",
        "implemented",
        ("item_attributes",),
        (),
        (r"duplicate|same (item|material) (twice|code)",),
        (69, 70, 71, 72, 73),
    ),
    Capability(
        "obsolescence",
        "Obsolescence and lifecycle review",
        "implemented",
        ("stock", "movements"),
        ("boms", "demand", "criticality"),
        (r"obsolet|dead stock|stop (buying|purchasing)|superseded|lifecycle",),
        (19, 20, 74, 75, 76, 77, 79),
    ),
    Capability(
        "safety_stock",
        "Safety-stock protection",
        "partial",
        ("stock",),
        ("demand",),
        (r"safety stock",),
        (16,),
        "Uses the maintained safety stock; statistical calculation needs demand and lead-time history.",
    ),
    Capability(
        "capacity",
        "Production capacity and bottlenecks",
        "planned",
        ("work_centres", "routings", "calendar"),
        (),
        (r"capacity|bottleneck|machine|work ?cent(er|re)|shift|downtime",),
        (35, 36, 37),
        "Needs work centres, routings and shift calendars, which no tenant provides yet.",
    ),
    Capability(
        "forecasting",
        "Demand forecasting and seasonality",
        "planned",
        ("movements",),
        (),
        (r"forecast|season|predict demand|demand trend",),
        (17, 18),
        "Needs reliable demand history; no forecast accuracy is claimed without it.",
    ),
    Capability(
        "make_or_buy",
        "Make-or-buy comparison",
        "partial",
        ("boms", "offers", "lead_times"),
        ("work_centres",),
        (r"make or buy|make-or-buy|outsourc|subcontract",),
        (32, 33),
        "Compares material availability, lead time and supplier price; internal cost and capacity need routings.",
    ),
)


@dataclass
class Assessment:
    question: str
    capabilities: list[str]
    known: dict[str, str]
    missing: dict[str, list[str]]  # capability → missing data keys
    capability_gaps: list[str]  # requested but not implemented
    questions: list[str]
    mode: Literal["full", "preliminary", "unsupported", "clarify"]
    notes: list[str] = field(default_factory=list)


def classify(question: str) -> list[Capability]:
    q = normalize(question)
    return [c for c in CAPABILITIES if any(re.search(t, q) for t in c.triggers)]


def assess(question: str, available: dict[str, int]) -> Assessment:
    """`available` maps data keys to record counts in the user's scope (0 or absent = not available)."""
    caps = classify(question)
    mode: Literal["full", "preliminary", "unsupported", "clarify"]
    known = {k: f"{n} records" for k, n in sorted(available.items()) if n}
    missing: dict[str, list[str]] = {}
    gaps: list[str] = []
    questions: list[str] = []
    notes: list[str] = []
    for c in caps:
        if c.status == "planned":
            gaps.append(f"{c.title}: {c.limitation}")
            continue
        miss = [k for k in c.requires if not available.get(k)]
        if miss:
            missing[c.name] = miss
            questions += [f"Can you provide {DATA_KEYS[k]}?" for k in miss]
        soft = [k for k in c.optional if not available.get(k)]
        if soft:
            notes.append(f"{c.title}: without {', '.join(DATA_KEYS[k] for k in soft)} the result is limited.")
        if c.status == "partial" and c.limitation:
            notes.append(f"{c.title}: {c.limitation}")
    runnable = [c for c in caps if c.status != "planned" and c.name not in missing]
    if not caps:
        mode = "clarify"
        questions.append("Which items, orders, warehouses or suppliers is this about, and what decision do you need?")
    elif runnable and not missing and not gaps:
        mode = "full"
    elif runnable:
        mode = "preliminary"
        notes.append(
            "Preliminary: parts of this question cannot be calculated with the data available; they are listed."
        )
    elif gaps and not missing:
        mode = "unsupported"
    else:
        mode = "clarify"
    return Assessment(
        question, [c.name for c in caps], known, missing, gaps, list(dict.fromkeys(questions)), mode, notes
    )
