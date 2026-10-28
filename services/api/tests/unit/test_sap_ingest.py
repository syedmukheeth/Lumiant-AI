"""SAP export importer: header contract, codes as text, exact decimals, total rows and the control-total gate."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb
import pytest
import yaml
from openpyxl import Workbook

from lumiant.core.config import BASE_DIR
from lumiant.ingest.sap_exports import (
    MASTER_COLUMNS,
    STOCK_COLUMNS,
    IntakeError,
    Kind,
    import_sap_exports,
    parse_cell,
)
from lumiant.synthetic.sap_twin import SAP_TWINS, build_rows, gamma_tenant_config

AS_OF = date(2026, 10, 1)
STOCK_HEADERS = [c.header for c in STOCK_COLUMNS]
MASTER_HEADERS = [c.header for c in MASTER_COLUMNS]
QTY = ["Unrestricted", "Quality Inspection", "Transit and Transfer", "Restricted-Use Stock", "Blocked", "Returns"]
VALUES = ["Value Unrestricted", "Value in QualInsp."]


def stock_row(
    material: str, uom: str, unr: Any, *, sloc: str = "0001", mtype: str = "ROH", **extra: Any
) -> dict[str, Any]:
    row = {
        "Plant": "P100",
        "Storage Location": sloc,
        "Material type": mtype,
        "Material Group": "G1",
        "Material": material,
        "Material Description": f"Item {material}",
        "Base Unit of Measure": uom,
        **dict.fromkeys(QTY, 0),
        **dict.fromkeys(VALUES, 0.0),
        "Unrestricted": unr,
    }
    row.update(extra)
    return row


def master_row(material: str, price: Any, per: int = 1, *, plant: str = "P100", uom: str = "EA") -> dict[str, Any]:
    return {
        "Material": material,
        "Plant": plant,
        "Valuation Type": "",
        "Material Description": f"Item {material}",
        "Last Change": datetime(2026, 3, 1),
        "Material type": "ROH",
        "Material Group": "G1",
        "Base Unit of Measure": uom,
        "Purchasing Group": "",
        "ABC Indicator": "",
        "MRP Type": "ND",
        "Valuation Class": "3000",
        "Price control": "V",
        "Price": price,
        "Currency": "SAR",
        "Price unit": per,
        "Created By": "PERSON1",
    }


def footer(details: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """SAP-style totals computed independently of the importer: per unit, values on the first row only."""
    rows = []
    for k, uom in enumerate(sorted({d["Base Unit of Measure"] for d in details})):
        row: dict[str, Any] = dict.fromkeys(STOCK_HEADERS[:7], "")
        row["Base Unit of Measure"] = uom
        for q in QTY:
            row[q] = float(sum(Decimal(str(d[q])) for d in details if d["Base Unit of Measure"] == uom))
        for v in VALUES:
            row[v] = float(sum(Decimal(str(d[v])) for d in details)) if k == 0 else None
        rows.append(row)
    return rows


def write_xlsx(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> Path:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h) for h in headers])
    wb.save(path)
    return path


DETAILS = [
    stock_row("000123", "EA", 10, Blocked=2, **{"Value Unrestricted": 25.5}),
    stock_row(
        "000456",
        "KG",
        1.5,
        sloc="0002",
        mtype="HALB",
        **{"Quality Inspection": 0.25, "Value in QualInsp.": 1.0, "Value Unrestricted": 6.0},
    ),
    stock_row("000789", "EA", 3, mtype="ZXYZ"),  # no master record
]
MASTER = [master_row("000123", 2.55), master_row("000456", 400.0, 100, uom="KG"), master_row("000999", 0, plant="P200")]


@pytest.fixture
def run(tmp_path: Path) -> Callable[..., Any]:
    def _run(
        details: list[dict[str, Any]] | None = None,
        master: list[dict[str, Any]] | None = None,
        totals: list[dict[str, Any]] | None = None,
        stock_headers: list[str] = STOCK_HEADERS,
    ) -> Any:
        details = [dict(d) for d in (DETAILS if details is None else details)]
        totals = footer(details) if totals is None else totals
        stock = write_xlsx(tmp_path / "stock.xlsx", stock_headers, details + totals)
        mast = write_xlsx(tmp_path / "master.xlsx", MASTER_HEADERS, MASTER if master is None else master)
        return import_sap_exports(
            stock, mast, tenant_id="t-test", as_of=AS_OF, target=tmp_path / "out" / "w.duckdb", synthetic=True
        )

    return _run


def connect(path: Path) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(path), read_only=True)


# --------------------------------------------------------------------------------------- cells
@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        ("000123", Kind.CODE, "000123"),
        (" 0042 ", Kind.CODE, "0042"),
        ("", Kind.CODE, None),
        (None, Kind.QUANTITY, None),
        (0.1, Kind.QUANTITY, Decimal("0.100")),
        (12, Kind.QUANTITY, Decimal("12.000")),
        (-0.0, Kind.AMOUNT, Decimal("0.00")),
        (1234567.89, Kind.AMOUNT, Decimal("1234567.89")),
        (100, Kind.INTEGER, 100),
        (datetime(2026, 1, 2, 3, 4), Kind.DATE, date(2026, 1, 2)),
    ],
)
def test_parse_cell(value: object, kind: Kind, expected: object) -> None:
    got = parse_cell(value, kind)
    assert got == expected
    if isinstance(expected, Decimal):
        assert str(got) == str(expected)  # exact scale, never a float


@pytest.mark.parametrize(
    ("value", "kind", "reason"),
    [
        (123, Kind.CODE, "leading zeros"),
        (1.0005, Kind.QUANTITY, "more than 3 decimal places"),
        (1.005, Kind.AMOUNT, "more than 2 decimal places"),
        ("12", Kind.AMOUNT, "expected a number"),
        (True, Kind.QUANTITY, "expected a number"),
        (float("nan"), Kind.AMOUNT, "not a finite number"),
        (1e16, Kind.AMOUNT, "too large"),
    ],
)
def test_parse_cell_refuses(value: object, kind: Kind, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        parse_cell(value, kind)


# --------------------------------------------------------------------------------------- import
def test_import_excludes_total_rows_and_keeps_them_as_control_totals(run: Callable[..., Any]) -> None:
    result = run()
    m = result.manifest
    assert m["control_totals"]["passed"] is True
    assert m["stock_total_rows_excluded"] == 2
    assert m["control_totals"]["value_totals"] == {"value_unrestricted": "31.50", "value_quality_inspection": "1.00"}
    with connect(result.target) as con:
        assert con.execute("SELECT count(*) FROM sap_mb52").fetchone() == (3,)
        assert con.execute("SELECT count(*) FROM sap_mb52_totals").fetchone() == (2,)
        # A naive sum over every row of the export would count the value twice.
        details = con.execute("SELECT sum(value_unrestricted) FROM sap_mb52").fetchone()
        totals = con.execute("SELECT sum(value_unrestricted) FROM sap_mb52_totals").fetchone()
        assert details == totals == (Decimal("31.50"),)
        lines = con.execute(
            "SELECT material, stock_status, quantity, valuation_price, currency FROM v_stock ORDER BY 1, 2"
        ).fetchall()
    assert lines == [
        ("000123", "blocked", Decimal("2.000"), Decimal("2.55000000"), "SAR"),
        ("000123", "unrestricted", Decimal("10.000"), Decimal("2.55000000"), "SAR"),
        ("000456", "quality_inspection", Decimal("0.250"), Decimal("4.00000000"), "SAR"),
        ("000456", "unrestricted", Decimal("1.500"), Decimal("4.00000000"), "SAR"),
        ("000789", "unrestricted", Decimal("3.000"), None, None),
    ]
    assert result.plants == ["P100", "P200"]


def test_manifest_reports_gaps_without_fixing_them(run: Callable[..., Any]) -> None:
    m = run().manifest
    assert m["stock"]["rows_without_master"] == 1
    assert m["stock"]["stocked_rows_without_master"] == 1
    assert m["stock"]["duplicate_keys"] == 0
    assert m["master"]["records_without_stock"] == 1
    assert m["master"]["zero_price"] == 1
    assert m["reconciliation"]["compared_lines"] == 3
    assert m["reconciliation"]["matching_lines"] == 3
    assert m["reconciliation"]["differing_lines"] == 0
    assert m["reconciliation"]["within_price_rounding_only"] == 0


def test_duplicate_stock_key_is_reported(run: Callable[..., Any]) -> None:
    details = [*DETAILS, stock_row("000123", "EA", 1, **{"Value Unrestricted": 2.55})]
    m = run(details=details).manifest
    assert m["stock"]["duplicate_keys"] == 1


def test_value_that_differs_from_quantity_times_price_is_counted(run: Callable[..., Any]) -> None:
    details = [dict(d) for d in DETAILS]
    details[0]["Value Unrestricted"] = 25.99
    m = run(details=details).manifest
    assert m["reconciliation"]["differing_lines"] == 1


def test_difference_explained_by_price_rounding_is_not_a_mismatch(run: Callable[..., Any]) -> None:
    # 10 units: a price shown to the cent can be up to 10 × 0.005 = 0.05 away from the stored value.
    details = [dict(d) for d in DETAILS]
    details[0]["Value Unrestricted"] = 25.54
    m = run(details=details).manifest
    assert m["reconciliation"]["differing_lines"] == 0
    assert m["reconciliation"]["within_price_rounding_only"] == 1
    details[0]["Value Unrestricted"] = 25.57
    assert run(details=details).manifest["reconciliation"]["differing_lines"] == 1


def test_created_by_is_not_stored(run: Callable[..., Any]) -> None:
    with connect(run().target) as con:
        cols = {r[0] for r in con.execute("DESCRIBE sap_material_master").fetchall()}
    assert "created_by" not in cols
    assert {"material", "plant", "price", "price_unit", "unit_price"} <= cols


def test_inexact_price_unit_leaves_the_line_unpriced(run: Callable[..., Any]) -> None:
    master = [master_row("000123", 10.0, 3), *MASTER[1:]]
    result = run(master=master)
    assert result.manifest["valuation_issues"] == {"inexact_price_unit": 1}
    with connect(result.target) as con:
        prices = con.execute("SELECT DISTINCT valuation_price FROM v_stock WHERE material = '000123'").fetchall()
    assert prices == [(None,)]


# --------------------------------------------------------------------------------------- the gate
def test_gate_fails_when_a_quantity_does_not_add_up(run: Callable[..., Any], tmp_path: Path) -> None:
    totals = footer(DETAILS)
    totals[0]["Unrestricted"] += 1
    with pytest.raises(IntakeError, match="nothing was written") as exc:
        run(totals=totals)
    assert any("unrestricted" in p for p in exc.value.problems)
    assert not (tmp_path / "out" / "w.duckdb").exists()


def test_gate_fails_when_the_value_total_does_not_add_up(run: Callable[..., Any]) -> None:
    totals = footer(DETAILS)
    totals[0]["Value Unrestricted"] = 31.6
    with pytest.raises(IntakeError, match="value_unrestricted"):
        run(totals=totals)


def test_gate_keeps_the_previous_database_when_it_fails(run: Callable[..., Any], tmp_path: Path) -> None:
    target = run().target
    before = target.read_bytes()
    totals = footer(DETAILS)
    totals[1]["Blocked"] = 5
    with pytest.raises(IntakeError):
        run(totals=totals)
    assert target.read_bytes() == before


def test_export_without_total_rows_is_refused(run: Callable[..., Any]) -> None:
    with pytest.raises(IntakeError, match="no SAP total rows"):
        run(totals=[])


def test_detail_row_after_the_totals_is_refused(run: Callable[..., Any], tmp_path: Path) -> None:
    rows = DETAILS[:2] + footer(DETAILS[:2]) + DETAILS[2:]
    stock = write_xlsx(tmp_path / "s.xlsx", STOCK_HEADERS, rows)
    master = write_xlsx(tmp_path / "m.xlsx", MASTER_HEADERS, MASTER)
    with pytest.raises(IntakeError, match="detail row after the SAP total rows"):
        import_sap_exports(stock, master, tenant_id="t", as_of=AS_OF, target=tmp_path / "x.duckdb", synthetic=True)


def test_one_value_total_row_is_required(run: Callable[..., Any]) -> None:
    totals = footer(DETAILS)
    totals[1]["Value Unrestricted"] = 0.0
    totals[1]["Value in QualInsp."] = 0.0
    with pytest.raises(IntakeError, match="exactly one total row with value totals"):
        run(totals=totals)


# --------------------------------------------------------------------------------------- contract
def test_missing_and_unexpected_columns_are_named(run: Callable[..., Any]) -> None:
    headers = [h if h != "Blocked" else "Blocked Stock" for h in STOCK_HEADERS]
    with pytest.raises(IntakeError) as exc:
        run(stock_headers=headers)
    text = str(exc.value)
    assert "missing columns: Blocked" in text
    assert "unexpected columns: 'Blocked Stock'" in text


def test_code_stored_as_a_number_is_refused_without_echoing_it(run: Callable[..., Any]) -> None:
    details = [dict(d) for d in DETAILS]
    details[1]["Material"] = 987654
    with pytest.raises(IntakeError) as exc:
        run(details=details)
    assert "row 3, Material" in str(exc.value)
    assert "987654" not in str(exc.value)


def test_split_valuation_is_refused(run: Callable[..., Any]) -> None:
    master = [*MASTER, master_row("000123", 2.60)]
    with pytest.raises(IntakeError, match="more than once"):
        run(master=master)


# --------------------------------------------------------------------------------------- twin
def test_twin_is_deterministic() -> None:
    profile = SAP_TWINS["demo-gamma"]
    assert build_rows(profile, AS_OF, 40) == build_rows(profile, AS_OF, 40)


def test_gamma_tenant_file_matches_the_generator() -> None:
    committed = yaml.safe_load((BASE_DIR / "config" / "tenants" / "demo-gamma.yaml").read_text(encoding="utf-8"))
    assert committed == gamma_tenant_config()
