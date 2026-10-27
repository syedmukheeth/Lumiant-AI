"""Synthetic tenant profiles: business shape of each demo tenant (ids must match the tenant YAML)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class GroupSpec:
    code: int  # alpha item-code category digits
    abbr: str  # beta item-code prefix
    weight: int
    stages: dict[str, float]
    uoms: tuple[str, ...]
    price: tuple[float, float]  # base unit price range in USD
    lot_tracked: float  # probability
    shelf_life_days: tuple[int, int] | None = None
    temp_range: tuple[tuple[int, int], ...] | None = None
    flammability: tuple[str, ...] | None = None
    demand: tuple[float, float] = (1.0, 50.0)  # units per month


GROUPS: dict[str, GroupSpec] = {
    "RUBBER": GroupSpec(
        11,
        "RB",
        14,
        {"RAW": 0.4, "SEMI": 0.15, "FINISHED": 0.3, "SPARE": 0.15},
        ("EA", "KG"),
        (1.5, 60),
        1.0,
        (1095, 1825),
        ((5, 30),),
        None,
        (20, 400),
    ),
    "FLAMMABLE": GroupSpec(
        12,
        "FL",
        8,
        {"RAW": 0.8, "SEMI": 0.2},
        ("L",),
        (3, 90),
        1.0,
        (365, 730),
        ((5, 30),),
        ("2", "3"),
        (10, 300),
    ),
    "TEMP_SENSITIVE": GroupSpec(
        13,
        "TS",
        8,
        {"RAW": 0.7, "SEMI": 0.3},
        ("KG",),
        (8, 250),
        1.0,
        (90, 365),
        ((2, 8), (15, 25)),
        None,
        (5, 150),
    ),
    "MECH_SPARES": GroupSpec(21, "MS", 22, {"SPARE": 1.0}, ("EA",), (15, 4500), 0.0, demand=(0.3, 12)),
    "ELECTRICAL": GroupSpec(
        22, "EL", 18, {"SPARE": 0.5, "RAW": 0.3, "FINISHED": 0.2}, ("EA",), (2, 900), 0.1, demand=(1, 60)
    ),
    "PACKAGING": GroupSpec(31, "PK", 15, {"RAW": 1.0}, ("EA",), (0.05, 5), 0.0, demand=(200, 5000)),
    "FASTENERS": GroupSpec(32, "FS", 15, {"RAW": 0.6, "SPARE": 0.4}, ("EA",), (0.01, 2), 0.0, demand=(100, 3000)),
}


@dataclass(frozen=True)
class WarehouseSpec:
    id: str
    name: str
    department: str
    site: str
    currency: str
    stages: tuple[str, ...]
    temperature_controlled: bool
    flammable_storage: bool
    locations: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class TenantProfile:
    tenant_id: str
    seed: int
    n_items: int
    months: int
    departments: tuple[tuple[str, str], ...]
    warehouses: tuple[WarehouseSpec, ...]
    code_style: str  # "numeric10" | "alnum"
    n_suppliers: int
    countries: tuple[str, ...]
    fx_from_usd: dict[str, Decimal] = field(default_factory=dict)
    attributes: tuple[str, ...] = ("colour", "material", "handling_note")


PROFILES: dict[str, TenantProfile] = {
    "demo-alpha": TenantProfile(
        tenant_id="demo-alpha",
        seed=20261026,
        n_items=600,
        months=24,
        departments=(
            ("NORTH", "North Plant Operations"),
            ("SOUTH", "South Plant Operations"),
            ("DIST", "Central Distribution"),
        ),
        warehouses=(
            WarehouseSpec(
                "1100",
                "North Plant — Raw Materials Store",
                "NORTH",
                "Northfield",
                "USD",
                ("RAW", "SEMI"),
                True,
                True,
                (("0001", "Main store"), ("0002", "Cold room"), ("0003", "Hazmat cage")),
            ),
            WarehouseSpec(
                "1110",
                "North Plant — Finished Goods",
                "NORTH",
                "Northfield",
                "USD",
                ("FINISHED", "SEMI"),
                False,
                False,
                (("0001", "Main store"), ("0002", "High-bay racking")),
            ),
            WarehouseSpec(
                "1120",
                "North Plant — Maintenance Spares",
                "NORTH",
                "Northfield",
                "USD",
                ("SPARE",),
                False,
                False,
                (("0001", "Spares crib"), ("0002", "Heavy parts yard")),
            ),
            WarehouseSpec(
                "2100",
                "South Plant — Raw Materials Store",
                "SOUTH",
                "Southport",
                "USD",
                ("RAW", "SEMI", "SPARE"),
                True,
                False,
                (("0001", "Main store"), ("0002", "Cold room")),
            ),
            WarehouseSpec(
                "2110",
                "South Plant — Finished Goods",
                "SOUTH",
                "Southport",
                "USD",
                ("FINISHED",),
                False,
                False,
                (("0001", "Main store"),),
            ),
            WarehouseSpec(
                "3100",
                "Central Distribution Center",
                "DIST",
                "Midvale",
                "USD",
                ("FINISHED",),
                False,
                False,
                (("0001", "Pick face"), ("0002", "Reserve racking")),
            ),
        ),
        code_style="numeric10",
        n_suppliers=24,
        countries=("US", "CA", "MX", "DE", "CN", "JP"),
        fx_from_usd={"USD": Decimal("1")},
    ),
    "demo-beta": TenantProfile(
        tenant_id="demo-beta",
        seed=20261027,
        n_items=250,
        months=24,
        departments=(("OPS_NL", "Netherlands Operations"), ("OPS_UK", "UK Operations")),
        warehouses=(
            WarehouseSpec(
                "RTM1",
                "Rotterdam Distribution Centre",
                "OPS_NL",
                "Rotterdam",
                "EUR",
                ("FINISHED", "RAW"),
                True,
                True,
                (("RTM1-A01", "Aisle A"), ("RTM1-B01", "Aisle B"), ("RTM1-C01", "Cold store")),
            ),
            WarehouseSpec(
                "ANT1",
                "Antwerp Spares Hub",
                "OPS_NL",
                "Antwerp",
                "EUR",
                ("SPARE",),
                False,
                False,
                (("ANT1-S01", "Spares shelving"),),
            ),
            WarehouseSpec(
                "LDS1",
                "Leeds Plant Stores",
                "OPS_UK",
                "Leeds",
                "GBP",
                ("RAW", "SEMI", "FINISHED", "SPARE"),
                True,
                True,
                (("LDS1-M01", "Main store"), ("LDS1-H01", "Hazmat store")),
            ),
        ),
        code_style="alnum",
        n_suppliers=14,
        countries=("NL", "BE", "DE", "GB", "PL", "IT"),
        fx_from_usd={"EUR": Decimal("0.92"), "GBP": Decimal("0.79")},
        attributes=("colour", "material", "humidity_max_pct", "handling_note"),
    ),
}
