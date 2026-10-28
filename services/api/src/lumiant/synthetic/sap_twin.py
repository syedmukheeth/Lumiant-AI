"""Synthetic twin of the client SAP exports (tenant demo-gamma, docs/04-domain/SYNTHETIC_DATA.md).

Writes two XLSX files with exactly the client's column layout — an MB52-style stock list with SAP total rows
and a material master valuation list — filled with generated values only, then the normal importer loads them.
Every data-quality check has at least one planted case; the planted counts are returned as `scenarios`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from openpyxl import Workbook

from lumiant.ingest.sap_exports import MASTER_COLUMNS, QTY_COLUMNS, STOCK_COLUMNS, VALUE_COLUMNS, sap_tenant_config

STOCK_PLANT = "GM01"
OTHER_PLANTS = ("GM02", "GM03")
CURRENCY = "SAR"
UNMAPPED_TYPE = "ZDMO"  # deliberately absent from the SAP standard value map
# (material type, weight, valuation class, description nouns)
TYPES: tuple[tuple[str, int, str, tuple[str, ...]], ...] = (
    ("ROH", 30, "3000", ("RESIN", "STEEL SHEET", "COPPER ROD", "PIGMENT", "SOLVENT")),
    ("HALB", 10, "7900", ("SUBASSEMBLY", "MACHINED HOUSING", "COATED PANEL")),
    ("FERT", 14, "7920", ("PUMP UNIT", "VALVE ASSY", "CONTROL CABINET")),
    ("HAWA", 5, "3100", ("TRADED FILTER", "TRADED HOSE")),
    ("ERSA", 22, "3040", ("BEARING", "GASKET", "SEAL KIT", "V-BELT", "FUSE")),
    ("VERP", 5, "3050", ("CARTON", "PALLET WRAP", "DRUM")),
    ("HIBE", 12, "3030", ("LUBRICANT", "GLOVES", "CLEANING AGENT")),
    (UNMAPPED_TYPE, 2, "3990", ("DEMO ITEM",)),
)
UOMS = (("EA", 58), ("KG", 15), ("M", 8), ("L", 7), ("PC", 6), ("ROL", 4), ("SET", 2))
MRP = (("ND", 74), ("VB", 15), ("PD", 7), ("VV", 2), ("", 2))
STATUS_ODDS = {
    "quality_inspection": 0.05,
    "transit_transfer": 0.01,
    "restricted_use": 0.01,
    "blocked": 0.02,
    "returns": 0.01,
}
CENT = Decimal("0.01")


@dataclass(frozen=True)
class TwinProfile:
    seed: int
    n_materials: int
    storage_locations: int = 29


SAP_TWINS = {"demo-gamma": TwinProfile(seed=20261027, n_materials=1500)}


def _pick(rng: random.Random, weighted: tuple[tuple[str, int], ...]) -> str:
    return rng.choices([v for v, _ in weighted], weights=[w for _, w in weighted])[0]


def _num(d: Decimal) -> int | float:
    """SAP list exports arrive as Excel numbers: integers or binary floats (exact for these magnitudes)."""
    return int(d) if d == d.to_integral_value() else float(d)


def _quantity(rng: random.Random, uom: str) -> Decimal:
    if uom in ("EA", "PC", "SET", "ROL"):
        return Decimal(rng.randint(1, 400))
    return Decimal(str(round(rng.uniform(0.5, 900), 3)))


def build_rows(profile: TwinProfile, as_of: date, n_materials: int | None = None) -> dict[str, Any]:
    rng = random.Random(profile.seed)
    n = n_materials or profile.n_materials
    slocs = [f"S{i:03d}" for i in range(1, profile.storage_locations - 1)] + ["QA01", "RT01"]
    type_weights = tuple((t, w) for t, w, _, _ in TYPES)
    by_type = {t: (vc, nouns) for t, _, vc, nouns in TYPES}
    master: list[dict[str, Any]] = []
    stock: list[dict[str, Any]] = []
    planted = dict.fromkeys(
        (
            "stock_without_master",
            "zero_price_with_stock",
            "value_mismatch",
            "duplicate_key",
            "unmapped_material_type",
            "inexact_price_unit",
            "master_without_stock",
            "other_plant_records",
        ),
        0,
    )
    for i in range(n):
        # 9-digit numbers with leading zeros (they must survive the import as text), a few 10-digit ones.
        material = f"{4_100_000 + i * 7:09d}" if i % 25 else f"{1_000_000_000 + i:010d}"
        mtype = _pick(rng, type_weights)
        valuation_class, nouns = by_type[mtype]
        uom = _pick(rng, UOMS)
        group = f"DG-{mtype[:3]}{rng.randint(1, 12):03d}"
        description = f"{rng.choice(nouns)} {rng.randint(10, 999)}"
        per_unit = Decimal(str(max(0.05, round(math.exp(rng.gauss(3.2, 1.5)), 2))))
        price_unit = 100 if rng.random() < 0.05 else 1
        price = (per_unit * price_unit).quantize(CENT)
        if mtype == UNMAPPED_TYPE:
            planted["unmapped_material_type"] += 1
        role = "normal"
        if i % 97 == 5:
            role = "no_master"
        elif i % 89 == 7:
            role = "zero_price"
        elif i % 53 == 11:
            role = "master_only"
        elif i == 13:
            role = "inexact_unit"
        if role == "zero_price":
            price = Decimal("0.00")
        if role == "inexact_unit":
            price, price_unit = Decimal("10.00"), 3
            planted["inexact_price_unit"] += 1
        base = {
            "Material": material,
            "Material Description": description,
            "Material type": mtype,
            "Material Group": group,
            "Base Unit of Measure": uom,
        }
        changed = datetime.combine(as_of - timedelta(days=rng.randint(1, 1100)), time())
        record = {
            **base,
            "Valuation Type": "",
            "Last Change": changed,
            "Purchasing Group": "" if rng.random() < 0.7 else f"P{rng.randint(1, 5):02d}",
            "ABC Indicator": "" if rng.random() < 0.97 else rng.choice("ABC"),
            "MRP Type": _pick(rng, MRP),
            "Valuation Class": valuation_class,
            "Price control": "S" if rng.random() < 0.12 else "V",
            "Price": price,
            "Currency": CURRENCY,
            "Price unit": price_unit,
            "Created By": f"SYNUSR{rng.randint(1, 4)}",
        }
        if role != "no_master":
            master.append({**record, "Plant": STOCK_PLANT})
        if i % 4 == 0:
            master.append({**record, "Plant": rng.choice(OTHER_PLANTS)})
            planted["other_plant_records"] += 1
        if role == "master_only":
            planted["master_without_stock"] += 1
            continue
        unit_price = None if role in ("no_master", "inexact_unit") else price / price_unit
        stocked_any = False
        for sloc in rng.sample(slocs, rng.randint(1, 6)):
            row: dict[str, Any] = {**base, "Plant": STOCK_PLANT, "Storage Location": sloc}
            row.update(dict.fromkeys(("Unrestricted", "Quality Inspection", "Transit and Transfer"), Decimal(0)))
            row.update(dict.fromkeys(("Restricted-Use Stock", "Blocked", "Returns"), Decimal(0)))
            if rng.random() >= 0.86 or (role != "normal" and not stocked_any):
                stocked_any = True
                row["Unrestricted"] = _quantity(rng, uom)
                for col, header in (
                    ("quality_inspection", "Quality Inspection"),
                    ("transit_transfer", "Transit and Transfer"),
                    ("restricted_use", "Restricted-Use Stock"),
                    ("blocked", "Blocked"),
                    ("returns", "Returns"),
                ):
                    if rng.random() < STATUS_ODDS[col]:
                        row[header] = _quantity(rng, uom)
            for qty_header, value_header in (
                ("Unrestricted", "Value Unrestricted"),
                ("Quality Inspection", "Value in QualInsp."),
            ):
                value = (
                    Decimal(0) if unit_price is None else (row[qty_header] * unit_price).quantize(CENT, ROUND_HALF_UP)
                )
                row[value_header] = value
            stock.append(row)
        if role == "no_master":
            planted["stock_without_master"] += 1
        if role == "zero_price":
            planted["zero_price_with_stock"] += 1
    valued = [r for r in stock if r["Value Unrestricted"] > 0]
    for r in valued[3::150]:  # moving-average drift: SAP value no longer equals quantity × price
        r["Value Unrestricted"] += Decimal("7.31")
        planted["value_mismatch"] += 1
    stock.append(dict(valued[1]))  # the same plant / storage location / material key on a second line
    planted["duplicate_key"] += 1
    return {"stock": stock, "master": master, "scenarios": planted}


def _totals(stock: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SAP footer: one row per unit of measure with quantity totals; the first also carries the value totals."""
    headers = {c.name: c.header for c in STOCK_COLUMNS}
    uoms = sorted({r["Base Unit of Measure"] for r in stock})
    rows = []
    for k, uom in enumerate(uoms):
        row: dict[str, Any] = {c.header: "" for c in STOCK_COLUMNS[:7]}
        row["Base Unit of Measure"] = uom
        for q in QTY_COLUMNS:
            row[headers[q]] = sum((r[headers[q]] for r in stock if r["Base Unit of Measure"] == uom), Decimal(0))
        for v in VALUE_COLUMNS:
            row[headers[v]] = sum((r[headers[v]] for r in stock), Decimal(0)) if k == 0 else None
        rows.append(row)
    return rows


def _write(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Sheet1")
    ws.append(headers)
    for r in rows:
        ws.append([_num(v) if isinstance(v, Decimal) else v for v in (r.get(h) for h in headers)])
    wb.save(path)


GAMMA_HEADER = """SYNTHETIC demo tenant: twin of the client SAP exports (same layout, generated values only).
Written by `sap_tenant_config` (lumiant.ingest.sap_exports) — the same mapping the client extract gets;
tests/unit/test_sap_ingest.py keeps this file and the generator in sync. Plant codes are invented."""


def gamma_tenant_config() -> dict[str, Any]:
    return sap_tenant_config(
        tenant_id="demo-gamma",
        display_name="Demo Gamma SAP extract twin (synthetic)",
        data_classification="synthetic",
        source_system="Synthetic SAP exports in the client layout (MB52 stock list + material master)",
        connection_path="data/synthetic/demo-gamma.duckdb",
        plants=sorted((STOCK_PLANT, *OTHER_PLANTS)),
        dev_users=[
            {"username": "gamma.admin", "display_name": "Gita Admin", "roles": ["super_admin"], "warehouses": ["*"]},
            {
                "username": "gamma.viewer",
                "display_name": "Gus Viewer (no cost access)",
                "roles": ["viewer_no_cost"],
                "warehouses": [STOCK_PLANT],
            },
        ],
    )


def write_twin_exports(
    directory: Path, profile: TwinProfile, *, as_of: date, n_materials: int | None = None
) -> tuple[Path, Path, dict[str, int]]:
    built = build_rows(profile, as_of, n_materials)
    directory.mkdir(parents=True, exist_ok=True)
    stock_path = directory / "Warehouse Stocks of Material.XLSX"
    master_path = directory / "Material Master.XLSX"
    _write(stock_path, [c.header for c in STOCK_COLUMNS], built["stock"] + _totals(built["stock"]))
    _write(master_path, [c.header for c in MASTER_COLUMNS], built["master"])
    return stock_path, master_path, built["scenarios"]
