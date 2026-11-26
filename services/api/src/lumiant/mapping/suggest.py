"""Suggest how a source's tables map onto the canonical inventory model (V2, docs/AI_SCHEMA_DISCOVERY.md §3).

Metadata only: table and column names and types; no row values are read. Signals, strongest first: column names known
in standard systems (SAP field names, common ERP names), the canonical field name itself, then table-name hints. Every
suggestion carries a confidence and the reason; nothing is applied until a person approves the mapping (it becomes
tenant configuration, reviewed like code, ADR-0006) and reconciliation passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lumiant.canonical.catalog import CATALOG

MAX_TABLES = 300

# Column names that mean a canonical field, normalised (lower case, letters and digits only). First match wins.
SYNONYMS: dict[str, tuple[str, ...]] = {
    "item_id": (
        "itemid",
        "item",
        "itemno",
        "itemnumber",
        "material",
        "materialid",
        "matnr",
        "sku",
        "productid",
        "partno",
        "partnumber",
        "inventoryitemid",
        "itemcode",
    ),
    "item_code": ("itemcode", "code", "defaultcode", "sku", "matnr", "segment1", "partnumber"),
    "description": ("description", "maktx", "itemname", "productname", "itemdescription", "name", "desc"),
    "item_group": ("itemgroup", "matkl", "productgroup", "itemcategory", "category", "group", "categid"),
    "inventory_stage": ("inventorystage", "stage", "mtart", "materialtype", "itemtype"),
    "abc_class": ("abcclass", "abc", "abckz", "abcindicator", "maabc"),
    "base_uom": ("baseuom", "meins", "uom", "unit", "unitofmeasure", "uomid"),
    "warehouse_id": (
        "warehouseid",
        "warehouse",
        "warehousecode",
        "werks",
        "plant",
        "plantcode",
        "site",
        "sitecode",
        "wh",
        "whse",
        "inventlocationid",
        "organizationid",
        "bwkey",
    ),
    "location_id": ("locationid", "location", "lgort", "bin", "bincode", "storagelocation", "subinventory", "sloc"),
    "lot_id": ("lotid", "lot", "lotnumber", "lotno", "batch", "batchno", "batchnumber", "charg", "inventbatchid"),
    "quantity": (
        "quantity",
        "qty",
        "qtyonhand",
        "onhand",
        "quantityonhand",
        "labst",
        "menge",
        "physicalinvent",
        "primarytransactionquantity",
    ),
    "uom": ("uom", "meins", "unit", "unitofmeasure", "uomid"),
    "valuation_price": (
        "valuationprice",
        "verpr",
        "unitvalue",
        "unitcost",
        "avgcost",
        "averagecost",
        "standardcost",
        "stprs",
        "movingaverageprice",
        "cost",
    ),
    "currency": ("currency", "currencycode", "waers", "curr", "currencyid"),
    "stock_status": ("stockstatus", "stocktype", "insmk", "status"),
    "txn_id": ("txnid", "transactionid", "movementid", "mblnr", "documentno", "docno", "moveid", "voucher"),
    "txn_type": ("txntype", "movementtype", "transactiontype", "bwart", "movetype", "type"),
    "posting_date": (
        "postingdate",
        "postedon",
        "postedat",
        "budat",
        "transactiondate",
        "transdate",
        "movementdate",
        "date",
    ),
    "unit_cost": ("unitcost", "zzunitcost", "cost", "price"),
    "expiry_date": ("expirydate", "vfdat", "expiry", "expirationdate", "bestbefore", "expdate", "usebydate"),
    "receipt_date": ("receiptdate", "receiveddate", "hsdat", "receivedon", "receipt"),
    "reorder_level": ("reorderlevel", "reorderpoint", "minbe", "rop"),
    "min_stock": ("minstock", "minqty", "safetystock", "eisbe", "minimum"),
    "max_stock": ("maxstock", "maxqty", "mabst", "maximum"),
    "supplier_id": ("supplierid", "suppliercode", "supplier", "vendorid", "vendor", "vendorcode", "lifnr", "partnerid"),
    "name": ("name", "suppliername", "warehousename", "binname", "description"),
    "po_id": ("poid", "ponumber", "ebeln", "purchaseorder", "po", "orderno", "orderid"),
    "order_date": ("orderdate", "bedat", "dateorder", "podate"),
    "unit_price": ("unitprice", "netpr", "price"),
    "department_id": ("departmentid", "department", "bucode", "businessunit", "costcenter", "dept"),
    "status": ("status", "state"),
}

# Words in a table name that suggest a dataset.
TABLE_HINTS: dict[str, tuple[str, ...]] = {
    "item": ("itemmaster", "material", "item", "product", "mara", "makt", "inventtable"),
    "warehouse": ("warehouse", "plant", "site", "t001w", "location"),
    "storage_location": ("bin", "storagelocation", "sloc", "t001l", "subinventor"),
    "stock_balance": ("stockonhand", "onhand", "stock", "inventsum", "mard", "balance", "inventory"),
    "reorder_policy": ("reorder", "replenish", "minmax", "policy", "marc"),
    "lot": ("lot", "batch", "mch1", "mchb"),
    "inventory_transaction": ("movement", "transaction", "mseg", "ledger", "inventtrans", "stockmove"),
    "purchase_record": ("purchase", "poline", "ekpo", "purchline"),
    "supplier": ("supplier", "vendor", "lfa1"),
    "department": ("department", "businessunit", "dept", "costcenter"),
}
# Hints that only say "inventory-ish"; they never outweigh a specific hint of another dataset.
GENERIC_HINTS = frozenset({"stock", "inventory", "balance", "location", "item", "lot"})
CORE = (
    "item",
    "warehouse",
    "storage_location",
    "stock_balance",
    "reorder_policy",
    "lot",
    "inventory_transaction",
    "purchase_record",
    "supplier",
    "department",
)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


@dataclass
class TableMeta:
    schema: str | None
    name: str
    columns: list[str]

    @property
    def ref(self) -> str:
        """`schema.table`, without a database prefix and without the engine's default schema."""
        schema = (self.schema or "").split(".")[-1].strip('"')
        return f"{schema}.{self.name}" if schema and schema not in ("main", "public", "dbo") else self.name


@dataclass
class Candidate:
    table: TableMeta
    score: float
    fields: dict[str, str]
    missing_required: list[str]
    reasons: list[str] = field(default_factory=list)


def _match(dataset: str, table: TableMeta) -> Candidate:
    ds = CATALOG[dataset]
    by_norm = {_norm(c): c for c in table.columns}
    fields: dict[str, str] = {}
    used: set[str] = set()
    canon = [f for f in ds.fields.values() if not f.computed]
    for f in sorted(canon, key=lambda f: not f.required):  # required fields claim columns first
        names = (_norm(f.name), *SYNONYMS.get(f.name, ()))
        free = {k: c for k, c in by_norm.items() if c not in used or f.name == "item_code"}
        exact = next((free[n] for n in names if n in free), None)
        # Weaker: a longer synonym inside a column name (custom fields such as SAP's ZZDEPT).
        partial = exact or next((c for n in names if len(n) >= 4 for k, c in free.items() if n in k), None)
        if partial is not None:
            fields[f.name] = partial
            used.add(partial)
    required = [f.name for f in canon if f.required]
    missing = [r for r in required if r not in fields]
    optional = [f.name for f in canon if not f.required]
    table_n = _norm(table.name)
    own = [h for h in TABLE_HINTS.get(dataset, ()) if h in table_n]
    specific = [h for h in own if h not in GENERIC_HINTS]
    others = [h for d, hs in TABLE_HINTS.items() if d != dataset for h in hs if h not in GENERIC_HINTS and h in table_n]
    hinted = 1.0 if specific else 0.0 if others else 0.5 if own else 0.0
    ds_n = _norm(dataset)
    named = table_n in {ds_n, ds_n + "s", "v" + ds_n, "vw" + ds_n, ds_n + "master", ds_n + "view"}
    if named:  # the table is literally called after the dataset (often a prepared view)
        hinted = 1.0
    req_share = (len(required) - len(missing)) / len(required) if required else 0.0
    opt_share = sum(1 for o in optional if o in fields) / len(optional) if optional else 0.0
    score = 0.55 * req_share + 0.15 * min(1.0, opt_share * 2) + 0.30 * hinted + (0.1 if named else 0.0)
    reasons = [f"{len(required) - len(missing)} of {len(required)} required fields found by name"]
    if others and not specific:
        reasons.append(f"table name suggests another dataset ({others[0]})")
    elif hinted:
        reasons.append("table name fits")
    return Candidate(table, round(score, 3), fields, missing, reasons)


def _confidence(c: Candidate) -> str:
    if c.score >= 0.75 and not c.missing_required:
        return "high"
    return "medium" if c.score >= 0.5 else "low"


def suggest(tables: list[TableMeta]) -> dict[str, Any]:
    """Best table per canonical dataset, with field matches, confidence, and a YAML draft for review."""
    tables = [t for t in tables if not t.name.startswith("_")][:MAX_TABLES]
    ranked = {ds: sorted((_match(ds, t) for t in tables), key=lambda c: -c.score) for ds in CORE}
    taken: set[str] = set()
    picks: dict[str, Candidate | None] = {}
    # The most certain datasets choose first; a table serves one dataset.
    for ds in sorted(CORE, key=lambda d: -(ranked[d][0].score if ranked[d] else 0)):
        choice = next((c for c in ranked[ds] if c.table.ref not in taken), None)
        if (
            choice is None
            or choice.score < 0.35
            or choice.missing_required == [f.name for f in CATALOG[ds].fields.values() if f.required]
        ):
            picks[ds] = None
            continue
        picks[ds] = choice
        taken.add(choice.table.ref)
    out = []
    for ds in CORE:
        c = picks[ds]
        out.append(
            {
                "dataset": ds,
                "source": c.table.ref if c else None,
                "confidence": _confidence(c) if c else "none",
                "score": c.score if c else 0.0,
                "fields": c.fields if c else {},
                "missing_required": c.missing_required
                if c
                else [f.name for f in CATALOG[ds].fields.values() if f.required],
                "reasons": c.reasons if c else ["no table fits"],
                "alternatives": [
                    a.table.ref for a in ranked[ds][1:3] if a.score >= 0.6 and (not c or a.table.ref != c.table.ref)
                ],
            }
        )
    return {"datasets": out, "yaml": _yaml(out), "tables_read": len(tables)}


def _yaml(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Draft mapping suggested from table and column names. Review every line, fill what is missing, then run the",
        "# schema check and reconciliation before anyone relies on the figures.",
        "datasets:",
    ]
    for r in rows:
        if not r["source"]:
            lines.append(f"  # {r['dataset']}: no table found")
            continue
        lines.append(f"  {r['dataset']}:  # confidence: {r['confidence']}")
        lines.append(f"    source: {r['source']}")
        lines.append("    fields:")
        lines += [f"      {k}: {v}" for k, v in r["fields"].items()]
        lines += [f"      # {m}: ?  (required, not found)" for m in r["missing_required"]]
    return "\n".join(lines) + "\n"


def read_tables(connector: Any) -> list[TableMeta]:
    """Table and column names through a connector's catalog calls (no data)."""
    metas: list[TableMeta] = []
    for obj in connector.list_objects()[:MAX_TABLES]:
        if obj.name.startswith("_"):
            continue
        cols = [c.name for c in connector.describe(obj.schema, obj.name)]
        metas.append(TableMeta(obj.schema, obj.name, cols))
    return metas
