"""Canonical inventory model — the semantic layer every tenant maps onto (docs/02-architecture/DATA_MODEL.md).

Field metadata drives validation: types and roles decide which operators and aggregations are legal,
`sensitivity` drives the `cost:read` check, `scope_key` drives warehouse-scope injection, and
`currency_field` / `unit_field` drive the currency and UoM safety rails.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FieldType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    DATETIME = "datetime"
    BOOLEAN = "boolean"


class FieldRole(StrEnum):
    KEY = "key"
    DIMENSION = "dimension"
    MEASURE = "measure"
    DATE = "date"
    ATTRIBUTE = "attribute"


class Sensitivity(StrEnum):
    NONE = "none"
    COST = "cost"


@dataclass(frozen=True)
class FieldDef:
    name: str
    type: FieldType
    role: FieldRole
    description: str
    sensitivity: Sensitivity = Sensitivity.NONE
    scope_key: bool = False
    unit_field: str | None = None
    currency_field: str | None = None
    # Computed fields are the product of two mapped fields of the same dataset (e.g. stock_value).
    product_of: tuple[str, str] | None = None
    required: bool = False

    @property
    def computed(self) -> bool:
        return self.product_of is not None

    @property
    def numeric(self) -> bool:
        return self.type in (FieldType.DECIMAL, FieldType.INTEGER)


@dataclass(frozen=True)
class JoinDef:
    """An approved many-to-one join from a dataset to a lookup dataset."""

    name: str
    dataset: str
    on: tuple[tuple[str, str], ...]  # (local field, remote field) pairs


@dataclass(frozen=True)
class DatasetDef:
    name: str
    description: str
    fields: dict[str, FieldDef]
    joins: dict[str, JoinDef] = field(default_factory=dict)

    @property
    def scope_field(self) -> str | None:
        return next((f.name for f in self.fields.values() if f.scope_key), None)

    @property
    def required_fields(self) -> list[str]:
        return [f.name for f in self.fields.values() if f.required]


S, INT, D, DT, B = (
    FieldType.STRING,
    FieldType.INTEGER,
    FieldType.DECIMAL,
    FieldType.DATE,
    FieldType.BOOLEAN,
)
KEY, DIM, MEA, DAT, ATT = (
    FieldRole.KEY,
    FieldRole.DIMENSION,
    FieldRole.MEASURE,
    FieldRole.DATE,
    FieldRole.ATTRIBUTE,
)
COST = Sensitivity.COST


def _fields(*defs: FieldDef) -> dict[str, FieldDef]:
    return {d.name: d for d in defs}


def _warehouse_id(description: str = "Warehouse / plant identifier") -> FieldDef:
    return FieldDef("warehouse_id", S, KEY, description, scope_key=True, required=True)


CATALOG: dict[str, DatasetDef] = {
    "item": DatasetDef(
        "item",
        "Item master: descriptive attributes of each stock-keeping item.",
        _fields(
            FieldDef("item_id", S, KEY, "Stable item identifier", required=True),
            FieldDef("item_code", S, DIM, "Customer item code (coding rules are tenant-specific)"),
            FieldDef("description", S, ATT, "Item description (untrusted free text)"),
            FieldDef("item_group", S, DIM, "Item group, e.g. RUBBER, FLAMMABLE"),
            FieldDef("inventory_stage", S, DIM, "RAW, SEMI, FINISHED, SPARE or customer-defined"),
            FieldDef("abc_class", S, DIM, "ABC class as assigned in the source item master"),
            FieldDef("base_uom", S, DIM, "Base unit of measure"),
            FieldDef("status", S, DIM, "Item status, e.g. ACTIVE, BLOCKED"),
            FieldDef("lot_tracked", B, DIM, "Whether the item is managed in lots/batches"),
            FieldDef("shelf_life_days", INT, ATT, "Shelf life in days"),
            FieldDef("storage_temp_min", D, ATT, "Minimum storage temperature (°C)"),
            FieldDef("storage_temp_max", D, ATT, "Maximum storage temperature (°C)"),
            FieldDef("flammability_class", S, DIM, "Flammability / hazard class"),
            FieldDef("default_supplier_id", S, KEY, "Preferred supplier"),
            FieldDef("manufacturer", S, ATT, "Manufacturer name"),
            FieldDef("mpn", S, ATT, "Manufacturer part number"),
            FieldDef("lifecycle_status", S, DIM, "active, superseded or discontinued"),
            FieldDef("superseded_by", S, KEY, "Replacement item when superseded"),
            FieldDef("critical", B, DIM, "Critical item, e.g. maintenance spare for critical equipment"),
        ),
        {"supplier": JoinDef("supplier", "supplier", (("default_supplier_id", "supplier_id"),))},
    ),
    "warehouse": DatasetDef(
        "warehouse",
        "Warehouses / plants / stores.",
        _fields(
            _warehouse_id(),
            FieldDef("name", S, DIM, "Warehouse name"),
            FieldDef("department_id", S, KEY, "Owning department"),
            FieldDef("site", S, DIM, "Site / city"),
            FieldDef("temperature_controlled", B, DIM, "Has temperature-controlled storage"),
            FieldDef("flammable_storage", B, DIM, "Rated for flammable materials"),
        ),
        {"department": JoinDef("department", "department", (("department_id", "department_id"),))},
    ),
    "storage_location": DatasetDef(
        "storage_location",
        "Storage locations inside a warehouse.",
        _fields(
            FieldDef("location_id", S, KEY, "Storage location code (unique within a warehouse)", required=True),
            _warehouse_id(),
            FieldDef("name", S, DIM, "Location name"),
        ),
    ),
    "stock_balance": DatasetDef(
        "stock_balance",
        "On-hand stock snapshot per item, warehouse, location and lot.",
        _fields(
            FieldDef("item_id", S, KEY, "Item", required=True),
            _warehouse_id(),
            FieldDef("location_id", S, DIM, "Storage location"),
            FieldDef("lot_id", S, DIM, "Lot / batch (empty for items not lot-managed)"),
            FieldDef("quantity", D, MEA, "On-hand quantity", unit_field="uom", required=True),
            FieldDef("uom", S, DIM, "Unit of measure of the quantity", required=True),
            FieldDef(
                "valuation_price",
                D,
                ATT,
                "Unit valuation price as provided by the source system",
                sensitivity=COST,
                currency_field="currency",
            ),
            FieldDef("currency", S, DIM, "Currency of the valuation price"),
            FieldDef(
                "stock_value",
                D,
                MEA,
                "On-hand quantity × source valuation price",
                sensitivity=COST,
                currency_field="currency",
                product_of=("quantity", "valuation_price"),
            ),
            FieldDef(
                "stock_status",
                S,
                DIM,
                "Stock status: unrestricted, quality_inspection, in_transit, restricted, blocked or returns",
            ),
            FieldDef(
                "source_value",
                D,
                MEA,
                "Stock value as reported by the source system (may cover only some stock statuses)",
                sensitivity=COST,
                currency_field="currency",
            ),
            FieldDef(
                "price_rounding",
                D,
                ATT,
                "Largest rounding in the unit valuation price as the source shows it (e.g. half a cent ÷ price unit)",
                sensitivity=COST,
                currency_field="currency",
            ),
        ),
        {
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
            "warehouse": JoinDef("warehouse", "warehouse", (("warehouse_id", "warehouse_id"),)),
            "reorder_policy": JoinDef(
                "reorder_policy",
                "reorder_policy",
                (("item_id", "item_id"), ("warehouse_id", "warehouse_id")),
            ),
            "lot": JoinDef("lot", "lot", (("lot_id", "lot_id"),)),
            "item_warehouse": JoinDef(
                "item_warehouse",
                "item_warehouse",
                (("item_id", "item_id"), ("warehouse_id", "warehouse_id")),
            ),
        },
    ),
    "item_warehouse": DatasetDef(
        "item_warehouse",
        "Item master data per warehouse / plant: planning and valuation settings (e.g. SAP MARC/MBEW).",
        _fields(
            FieldDef("item_id", S, KEY, "Item", required=True),
            _warehouse_id(),
            FieldDef("abc_class", S, DIM, "ABC class assigned for this warehouse / plant"),
            FieldDef(
                "planning_type",
                S,
                DIM,
                "Stock planning type: none, reorder_point, mrp, forecast or customer-defined (via a value map)",
            ),
            FieldDef("price_control", S, DIM, "Valuation price control: moving_average or standard (via a value map)"),
            FieldDef(
                "valuation_price",
                D,
                ATT,
                "Unit valuation price for this warehouse / plant as provided by the source system",
                sensitivity=COST,
                currency_field="currency",
            ),
            FieldDef("currency", S, DIM, "Currency of the valuation price"),
            FieldDef("procurement_type", S, DIM, "make, buy or both (SAP BESKZ, Odoo routes)"),
            FieldDef("phantom", B, ATT, "Phantom assembly: exploded through, never stocked"),
            FieldDef("lead_days", INT, ATT, "Production or planned delivery lead time in working days"),
            FieldDef("receiving_days", INT, ATT, "Goods-receipt processing time in working days"),
            FieldDef("inspection_days", INT, ATT, "Quality inspection time in working days"),
            FieldDef("safety_stock", D, ATT, "Safety stock in the base unit"),
            FieldDef("lot_rule", S, ATT, "lot_for_lot, fixed, min_qty or multiple"),
            FieldDef("lot_size", D, ATT, "Fixed lot size"),
            FieldDef("min_lot", D, ATT, "Minimum lot size"),
            FieldDef("lot_multiple", D, ATT, "Order / production multiple"),
        ),
        {
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
            "warehouse": JoinDef("warehouse", "warehouse", (("warehouse_id", "warehouse_id"),)),
        },
    ),
    "reorder_policy": DatasetDef(
        "reorder_policy",
        "Customer-defined stock policy per item and warehouse.",
        _fields(
            FieldDef("item_id", S, KEY, "Item", required=True),
            _warehouse_id(),
            FieldDef("min_stock", D, ATT, "Minimum / safety stock"),
            FieldDef("max_stock", D, ATT, "Maximum stock"),
            FieldDef("reorder_level", D, ATT, "Reorder level (in the item's base UoM)", required=True),
        ),
        {
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
            "warehouse": JoinDef("warehouse", "warehouse", (("warehouse_id", "warehouse_id"),)),
        },
    ),
    "lot": DatasetDef(
        "lot",
        "Lots / batches with receipt and expiry dates.",
        _fields(
            FieldDef("lot_id", S, KEY, "Lot / batch", required=True),
            FieldDef("item_id", S, KEY, "Item", required=True),
            _warehouse_id("Receiving warehouse"),
            FieldDef("receipt_date", DT, DAT, "Receipt date"),
            FieldDef("expiry_date", DT, DAT, "Expiry date"),
            FieldDef("supplier_id", S, KEY, "Supplier"),
            FieldDef("unit_cost", D, ATT, "Lot unit cost at receipt", sensitivity=COST, currency_field="currency"),
            FieldDef("currency", S, DIM, "Currency of the unit cost"),
        ),
        {
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
            "warehouse": JoinDef("warehouse", "warehouse", (("warehouse_id", "warehouse_id"),)),
        },
    ),
    "inventory_transaction": DatasetDef(
        "inventory_transaction",
        "Stock movements (receipts, issues, transfers, adjustments, returns).",
        _fields(
            FieldDef("txn_id", S, KEY, "Movement document id", required=True),
            FieldDef(
                "txn_type",
                S,
                DIM,
                "RECEIPT, ISSUE, TRANSFER_IN, TRANSFER_OUT, ADJUSTMENT, RETURN",
                required=True,
            ),
            FieldDef("item_id", S, KEY, "Item", required=True),
            _warehouse_id(),
            FieldDef("location_id", S, DIM, "Storage location"),
            FieldDef("lot_id", S, DIM, "Lot / batch"),
            FieldDef("quantity", D, MEA, "Signed quantity (+ in, − out)", unit_field="uom", required=True),
            FieldDef("uom", S, DIM, "Unit of measure", required=True),
            FieldDef("unit_cost", D, ATT, "Unit cost of the movement", sensitivity=COST, currency_field="currency"),
            FieldDef("currency", S, DIM, "Currency of the unit cost"),
            FieldDef("posting_date", DT, DAT, "Posting date", required=True),
        ),
        {
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
            "warehouse": JoinDef("warehouse", "warehouse", (("warehouse_id", "warehouse_id"),)),
        },
    ),
    "purchase_record": DatasetDef(
        "purchase_record",
        "Purchase order lines.",
        _fields(
            FieldDef("po_id", S, KEY, "Purchase order", required=True),
            FieldDef("line", S, KEY, "Purchase order line"),
            FieldDef("item_id", S, KEY, "Item", required=True),
            FieldDef("supplier_id", S, KEY, "Supplier"),
            _warehouse_id("Receiving warehouse"),
            FieldDef("order_date", DT, DAT, "Order date"),
            FieldDef("receipt_date", DT, DAT, "Receipt date"),
            FieldDef("quantity", D, MEA, "Ordered quantity", unit_field="uom"),
            FieldDef("uom", S, DIM, "Unit of measure"),
            FieldDef("unit_price", D, ATT, "Unit purchase price", sensitivity=COST, currency_field="currency"),
            FieldDef("currency", S, DIM, "Currency of the unit price"),
            FieldDef("status", S, DIM, "Line status, e.g. OPEN, RECEIVED"),
            FieldDef("expected_date", DT, DAT, "Promised / expected delivery date"),
            FieldDef("open_quantity", D, MEA, "Quantity still expected", unit_field="uom"),
            FieldDef("received_quantity", D, MEA, "Quantity received", unit_field="uom"),
            FieldDef("rejected_quantity", D, MEA, "Quantity rejected at inspection", unit_field="uom"),
        ),
        {
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
            "supplier": JoinDef("supplier", "supplier", (("supplier_id", "supplier_id"),)),
            "warehouse": JoinDef("warehouse", "warehouse", (("warehouse_id", "warehouse_id"),)),
        },
    ),
    "supplier": DatasetDef(
        "supplier",
        "Suppliers / vendors.",
        _fields(
            FieldDef("supplier_id", S, KEY, "Supplier", required=True),
            FieldDef("name", S, DIM, "Supplier name"),
            FieldDef("country", S, DIM, "Country code"),
            FieldDef("approved", B, DIM, "Approved / qualified supplier"),
            FieldDef("status", S, DIM, "active, blocked or on_hold"),
            FieldDef("certification", S, ATT, "Mandatory certification held, e.g. ISO 9001"),
            FieldDef("certification_expiry", DT, DAT, "Expiry date of the mandatory certification"),
            FieldDef("currency", S, DIM, "Order currency"),
            FieldDef("payment_terms", S, ATT, "Payment terms"),
        ),
    ),
    # ------------------------------------------------------------------ planning (docs/MASTER_DATA_MODEL.md)
    "bom_component": DatasetDef(
        "bom_component",
        "Bill of materials lines with their header attributes (SAP STKO/STPO, Odoo mrp.bom(.line), Oracle structures).",
        _fields(
            FieldDef("bom_id", S, KEY, "BOM identifier", required=True),
            FieldDef("parent_item_id", S, KEY, "Item the BOM produces", required=True),
            FieldDef("revision", S, DIM, "Engineering revision"),
            FieldDef("alternative", S, DIM, "Alternative BOM / production method"),
            FieldDef("priority", INT, ATT, "Preference among valid alternatives (1 = preferred)"),
            FieldDef("base_quantity", D, ATT, "Parent quantity the component quantities refer to"),
            FieldDef("yield_pct", D, ATT, "Good output per input, percent"),
            FieldDef("status", S, DIM, "released, draft or obsolete"),
            FieldDef("valid_from", DT, DAT, "Effective from"),
            FieldDef("valid_to", DT, DAT, "Effective until (exclusive)"),
            FieldDef("component_item_id", S, KEY, "Component item", required=True),
            FieldDef("quantity", D, MEA, "Component quantity per base quantity", unit_field="uom", required=True),
            FieldDef("uom", S, DIM, "Unit of the component quantity"),
            FieldDef("scrap_pct", D, ATT, "Component scrap allowance, percent"),
            FieldDef("sequence", INT, ATT, "Line sequence"),
        ),
        {
            "parent": JoinDef("parent", "item", (("parent_item_id", "item_id"),)),
            "component": JoinDef("component", "item", (("component_item_id", "item_id"),)),
        },
    ),
    "item_alternate": DatasetDef(
        "item_alternate",
        "Approved substitute relationships between items.",
        _fields(
            FieldDef("item_id", S, KEY, "Primary item", required=True),
            FieldDef("alternate_item_id", S, KEY, "Alternate item", required=True),
            FieldDef("ratio", D, ATT, "Alternate units that replace one primary unit"),
            FieldDef("priority", INT, ATT, "Substitution priority (1 = first)"),
            FieldDef("approved", B, DIM, "Approved substitution"),
            FieldDef("valid_from", DT, DAT, "Effective from"),
            FieldDef("valid_to", DT, DAT, "Effective until (exclusive)"),
            FieldDef("max_share_pct", D, ATT, "Maximum share of a requirement that may be substituted"),
            FieldDef("customer_id", S, DIM, "If set, only for this customer"),
            FieldDef("note", S, ATT, "Technical compatibility note (untrusted free text)"),
        ),
    ),
    "supplier_item": DatasetDef(
        "supplier_item",
        "Supplier–item relationships and quotations "
        "(SAP purchasing info records, Odoo product.supplierinfo, Oracle ASL).",
        _fields(
            FieldDef("supplier_id", S, KEY, "Supplier", required=True),
            FieldDef("item_id", S, KEY, "Item", required=True),
            FieldDef("supplier_item_code", S, DIM, "Supplier's own item code"),
            FieldDef("price", D, ATT, "Quoted price per price unit", sensitivity=COST, currency_field="currency"),
            FieldDef("currency", S, DIM, "Quotation currency"),
            FieldDef("price_unit", D, ATT, "Units the price refers to"),
            FieldDef("uom", S, DIM, "Order unit"),
            FieldDef("moq", D, ATT, "Minimum order quantity"),
            FieldDef("order_multiple", D, ATT, "Order multiple"),
            FieldDef("lead_days", INT, ATT, "Supplier-specific planned delivery time, working days"),
            FieldDef("valid_from", DT, DAT, "Quotation valid from"),
            FieldDef("valid_to", DT, DAT, "Quotation valid until"),
            FieldDef("approved", B, DIM, "Approved source for this item"),
            FieldDef(
                "freight_per_unit",
                D,
                ATT,
                "Freight per unit, quotation currency",
                sensitivity=COST,
                currency_field="currency",
            ),
            FieldDef("duty_pct", D, ATT, "Import duty percent"),
            FieldDef("capacity", D, ATT, "Maximum quantity the supplier can deliver for a need"),
        ),
        {
            "supplier": JoinDef("supplier", "supplier", (("supplier_id", "supplier_id"),)),
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
        },
    ),
    "customer_order_line": DatasetDef(
        "customer_order_line",
        "Open customer (sales) order lines.",
        _fields(
            FieldDef("order_id", S, KEY, "Customer order", required=True),
            FieldDef("line", S, KEY, "Order line"),
            FieldDef("customer_id", S, DIM, "Customer"),
            FieldDef("item_id", S, KEY, "Item", required=True),
            _warehouse_id("Shipping warehouse / plant"),
            FieldDef("quantity", D, MEA, "Open quantity", unit_field="uom", required=True),
            FieldDef("uom", S, DIM, "Unit of measure"),
            FieldDef("due_date", DT, DAT, "Requested delivery date", required=True),
            FieldDef("priority", INT, ATT, "Order priority (1 = most important)"),
            FieldDef("order_date", DT, DAT, "Order date"),
            FieldDef("status", S, DIM, "OPEN, PARTIAL, CANCELLED …"),
            FieldDef("ship_days", INT, ATT, "Working days from dispatch to the customer"),
            FieldDef("unit_price", D, ATT, "Selling price per unit", sensitivity=COST, currency_field="currency"),
            FieldDef("currency", S, DIM, "Order currency"),
            FieldDef("margin_pct", D, ATT, "Contribution margin, percent of order value", sensitivity=COST),
            FieldDef(
                "penalty_per_day",
                D,
                ATT,
                "Contractual late-delivery penalty per working day",
                sensitivity=COST,
                currency_field="currency",
            ),
        ),
        {
            "item": JoinDef("item", "item", (("item_id", "item_id"),)),
            "warehouse": JoinDef("warehouse", "warehouse", (("warehouse_id", "warehouse_id"),)),
        },
    ),
    "department": DatasetDef(
        "department",
        "Departments that own warehouses.",
        _fields(
            FieldDef("department_id", S, KEY, "Department", required=True),
            FieldDef("name", S, DIM, "Department name"),
        ),
    ),
}


def get_dataset(name: str) -> DatasetDef | None:
    return CATALOG.get(name)
