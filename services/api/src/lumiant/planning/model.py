"""Planning domain records. Quantities and amounts are `Decimal`; dates are `date`; nothing here does I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)

# Stock statuses that may be issued today. Everything else (quality inspection, blocked, restricted, returns,
# damaged, quarantine, in transit, expired) is physically present but not usable (scenarios 10, 11).
USABLE_STATUSES = frozenset({"unrestricted", "available"})


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"  # the affected figure cannot be calculated reliably


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    message: str
    item_id: str | None = None
    reference: str | None = None


# ------------------------------------------------------------------------------------------------ master data
@dataclass(frozen=True)
class Item:
    item_id: str
    description: str = ""
    base_uom: str = "EA"
    item_group: str = ""
    stage: str = ""  # RAW, SEMI, FINISHED, SPARE …
    procurement: Literal["buy", "make", "both"] = "buy"
    phantom: bool = False  # planning structure: exploded through, never stocked or ordered (scenario 28)
    status: str = "ACTIVE"
    critical: bool = False  # e.g. maintenance spare for critical equipment (scenarios 20, 75)
    lifecycle: Literal["active", "superseded", "discontinued"] = "active"
    superseded_by: str | None = None
    manufacturer: str = ""
    mpn: str = ""  # manufacturer part number
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class UomConversion:
    from_uom: str
    to_uom: str
    factor: Decimal  # 1 from_uom = factor × to_uom
    item_id: str | None = None  # None = valid for every item


@dataclass(frozen=True)
class BomLine:
    component_id: str
    quantity: Decimal  # per `Bom.base_quantity` of the parent
    uom: str = ""
    scrap_pct: Decimal = ZERO  # component scrap: extra % of this component consumed (scenario 27)
    sequence: int = 10


@dataclass(frozen=True)
class Bom:
    bom_id: str
    item_id: str
    revision: str
    lines: tuple[BomLine, ...]
    base_quantity: Decimal = ONE
    valid_from: date | None = None
    valid_to: date | None = None  # exclusive
    status: Literal["released", "draft", "obsolete"] = "released"
    yield_pct: Decimal = HUNDRED  # good output per input (scenario 27)
    alternative: str = "1"  # alternative BOM / production method (scenario 29)
    priority: int = 1  # lower = preferred among valid alternatives

    def valid_on(self, day: date) -> bool:
        if self.status != "released":
            return False
        return (self.valid_from is None or self.valid_from <= day) and (self.valid_to is None or day < self.valid_to)


@dataclass(frozen=True)
class AlternateRule:
    """Approved substitute: `ratio` units of `alternate_id` replace one unit of `item_id` (scenarios 26, 42–45)."""

    item_id: str
    alternate_id: str
    ratio: Decimal = ONE
    priority: int = 1
    approved: bool = True
    valid_from: date | None = None
    valid_to: date | None = None
    max_share_pct: Decimal | None = None  # at most this % of a requirement may be substituted
    customers_only: tuple[str, ...] = ()  # if set, only for these customers
    customers_excluded: tuple[str, ...] = ()
    note: str = ""

    def usable(self, day: date, customers: frozenset[str]) -> tuple[bool, str]:
        if not self.approved:
            return False, "not approved"
        if (self.valid_from and day < self.valid_from) or (self.valid_to and day >= self.valid_to):
            return False, "not valid on the requirement date"
        if self.customers_only and not customers <= set(self.customers_only):
            return False, "restricted to other customers"
        if customers & set(self.customers_excluded):
            return False, "excluded for this customer"
        return True, ""


# ------------------------------------------------------------------------------------------------ stock & supply
@dataclass(frozen=True)
class StockLine:
    item_id: str
    warehouse_id: str
    quantity: Decimal
    uom: str
    status: str = "unrestricted"
    lot_id: str | None = None
    expiry: date | None = None
    owner: Literal["company", "customer", "consignment"] = "company"

    def usable_on(self, day: date) -> bool:
        return (
            self.status in USABLE_STATUSES
            and self.owner == "company"
            and (self.expiry is None or self.expiry > day)
            and self.quantity > 0
        )


@dataclass(frozen=True)
class Reservation:
    item_id: str
    warehouse_id: str
    quantity: Decimal
    reference: str = ""


@dataclass(frozen=True)
class Supply:
    """Scheduled receipt: open purchase order line, production order or transfer. Usable from `due` (scenario 14)."""

    reference: str
    item_id: str
    warehouse_id: str
    quantity: Decimal  # still expected (ordered − received − rejected)
    due: date
    uom: str = ""
    kind: Literal["purchase", "production", "transfer"] = "purchase"
    supplier_id: str | None = None


@dataclass(frozen=True)
class DemandLine:
    order_id: str
    line: str
    item_id: str
    warehouse_id: str
    quantity: Decimal
    due: date
    uom: str = ""
    customer_id: str = ""
    priority: int = 5  # 1 = most important
    order_date: date | None = None
    kind: Literal["customer_order", "forecast", "safety_stock", "dependent"] = "customer_order"
    ship_days: int = 0  # working days from dispatch to the customer; goods must be ready `ship_days` before `due`
    # Commercial facts for customer commitment protection (all optional; never guessed when missing).
    unit_price: Decimal | None = None
    currency: str = ""
    margin_pct: Decimal | None = None  # contribution margin, percent of order value
    penalty_per_day: Decimal | None = None  # contractual late-delivery penalty per working day late
    confirmed: bool = True

    @property
    def key(self) -> str:
        return f"{self.order_id}/{self.line}"

    @property
    def value(self) -> Decimal | None:
        return None if self.unit_price is None else self.quantity * self.unit_price


@dataclass(frozen=True)
class PlanningPolicy:
    """Per item (and optionally warehouse) planning parameters. `None` lead time means unknown, never zero."""

    item_id: str
    warehouse_id: str | None = None
    lot_rule: Literal["lot_for_lot", "fixed", "min_qty", "multiple"] = "lot_for_lot"
    lot_size: Decimal | None = None  # fixed order quantity
    min_lot: Decimal | None = None
    multiple: Decimal | None = None
    safety_stock: Decimal = ZERO
    lead_days: int | None = None  # production lead time (make) or planned delivery time (buy), working days
    receiving_days: int = 0
    inspection_days: int = 0
    procurement: Literal["buy", "make"] | None = None  # per plant (made in one plant, bought by a DC); None = item's


@dataclass(frozen=True)
class Calendar:
    """Working calendar. Default weekend Friday + Saturday (Saudi Arabia); `weekdays` uses Monday = 0."""

    weekend: frozenset[int] = frozenset({4, 5})
    holidays: frozenset[date] = frozenset()


@dataclass(frozen=True)
class AllocationPolicy:
    """Order in which competing demand consumes scarce supply (scenario 3). Configurable per tenant."""

    keys: tuple[Literal["due", "priority", "order_date", "quantity"], ...] = ("due", "priority", "order_date")
    protect_safety_stock: bool = True


# ------------------------------------------------------------------------------------------------ suppliers
@dataclass(frozen=True)
class Certification:
    name: str
    expires: date | None = None
    mandatory: bool = True


@dataclass(frozen=True)
class Supplier:
    supplier_id: str
    name: str = ""
    country: str = ""
    approved: bool = True
    status: str = "active"  # active, blocked, on_hold
    certifications: tuple[Certification, ...] = ()
    currency: str = ""
    payment_terms: str = ""
    risk: str = ""


@dataclass(frozen=True)
class PriceBreak:
    min_quantity: Decimal
    price: Decimal


@dataclass(frozen=True)
class SupplierOffer:
    """Supplier–item relationship / quotation (purchasing info record, approved supplier list entry)."""

    supplier_id: str
    item_id: str
    price: Decimal
    currency: str
    price_unit: Decimal = ONE  # price is per this many units
    uom: str = ""
    moq: Decimal = ZERO
    multiple: Decimal | None = None
    lead_days: int | None = None  # supplier-item specific; None = unknown
    valid_from: date | None = None
    valid_to: date | None = None
    approved: bool = True
    price_breaks: tuple[PriceBreak, ...] = ()
    capacity: Decimal | None = None  # max quantity the supplier can deliver for this need
    freight: Decimal | None = None  # per unit, offer currency; None = unknown, not zero
    duty_pct: Decimal | None = None
    other_charges: Decimal | None = None  # per unit
    reference: str = ""


@dataclass(frozen=True)
class DeliveryRecord:
    supplier_id: str
    item_id: str
    reference: str
    promised: date
    received: date | None
    quantity_ordered: Decimal
    quantity_received: Decimal = ZERO
    quantity_rejected: Decimal = ZERO


@dataclass(frozen=True)
class PriceRecord:
    supplier_id: str
    item_id: str
    day: date
    price: Decimal  # per base unit
    currency: str
    kind: Literal["purchase", "quotation"] = "purchase"


@dataclass(frozen=True)
class FxRate:
    from_currency: str
    to_currency: str
    rate: Decimal  # 1 from = rate × to
    valid_from: date


@dataclass(frozen=True)
class SupplierPolicy:
    """How a tenant ranks suppliers. There is no universal winner (scenarios 46–49, combined C)."""

    name: str = "balanced"
    mode: Literal["weighted", "cheapest", "fastest", "quality"] = "weighted"
    weights: dict[str, Decimal] = field(
        default_factory=lambda: {
            "price": Decimal("0.4"),
            "quality": Decimal("0.3"),
            "delivery": Decimal("0.2"),
            "lead_time": Decimal("0.1"),
        }
    )
    max_rejection_pct: Decimal | None = None  # quality gate; above it the offer is not eligible
    min_on_time_pct: Decimal | None = None
    min_evidence_lots: int = 3  # fewer inspected deliveries = insufficient quality evidence (scenario 57)
    require_mandatory_certifications: bool = True  # scenario 56
    base_currency: str = "SAR"
    require_need_date: bool = True  # an offer that cannot arrive in time is not eligible


@dataclass(frozen=True)
class PlanningData:
    """Everything one planning run may use; built by `loader.py` or by tests."""

    today: date
    items: dict[str, Item] = field(default_factory=dict)
    boms: tuple[Bom, ...] = ()
    alternates: tuple[AlternateRule, ...] = ()
    stock: tuple[StockLine, ...] = ()
    reservations: tuple[Reservation, ...] = ()
    supply: tuple[Supply, ...] = ()
    demand: tuple[DemandLine, ...] = ()
    policies: tuple[PlanningPolicy, ...] = ()
    conversions: tuple[UomConversion, ...] = ()
    calendar: Calendar = Calendar()
    allocation: AllocationPolicy = AllocationPolicy()

    def policy(self, item_id: str, warehouse_id: str) -> PlanningPolicy:
        exact = next((p for p in self.policies if p.item_id == item_id and p.warehouse_id == warehouse_id), None)
        if exact:
            return exact
        generic = next((p for p in self.policies if p.item_id == item_id and p.warehouse_id is None), None)
        return generic or PlanningPolicy(item_id)
