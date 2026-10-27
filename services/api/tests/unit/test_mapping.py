import sqlalchemy as sa

from lumiant.core.config import BASE_DIR
from lumiant.mapping.resolver import SourceObject, TenantMapping
from lumiant.tenancy.registry import TenantRegistry

REG = TenantRegistry.load(BASE_DIR / "config" / "tenants")
ALPHA = TenantMapping(REG.get("demo-alpha"))
BETA = TenantMapping(REG.get("demo-beta"))


def test_canonical_fields_resolve_to_tenant_columns() -> None:
    assert ALPHA.physical_column("stock_balance", "warehouse_id") == "WERKS"
    assert BETA.physical_column("stock_balance", "warehouse_id") == "warehouse_code"
    assert ALPHA.physical_ref("stock_balance", "quantity") == "ZV_STOCK.LABST"
    assert BETA.physical_ref("stock_balance", "quantity") == "inv.stock_on_hand.qty_on_hand"


def test_computed_field_available_when_operands_mapped() -> None:
    fdef = ALPHA.field("stock_balance", "stock_value")
    assert fdef is not None
    assert fdef.computed
    assert ALPHA.physical_ref("stock_balance", "stock_value") == "ZV_STOCK.LABST * ZV_STOCK.VERPR"


def test_unmapped_field_is_unavailable() -> None:
    # No tenant maps an invented field; availability is explicit only.
    assert ALPHA.field("stock_balance", "nonexistent") is None
    assert not ALPHA.is_mapped("ghost_dataset")


def test_attributes_are_exposed_with_prefix() -> None:
    assert ALPHA.field("item", "attr_colour") is not None
    assert BETA.field("item", "attr_humidity_max_pct") is not None
    assert ALPHA.field("item", "attr_humidity_max_pct") is None


def test_shared_physical_column_appears_once() -> None:
    table = ALPHA.table("item")
    assert [c.name for c in table.columns].count("MATNR") == 1


def test_schema_qualified_sources() -> None:
    table = BETA.table("stock_balance")
    assert table.schema == "inv"
    assert table.name == "stock_on_hand"
    assert SourceObject.parse("inv.lots").qualified == "inv.lots"
    assert "inv.stock_on_hand" in BETA.physical_tables()


def test_column_expr_for_computed_field_multiplies_columns() -> None:
    t = ALPHA.table("stock_balance").alias("b")
    expr = ALPHA.column_expr("stock_balance", "stock_value", t)
    sql = str(sa.select(expr).compile())
    assert '"LABST"' in sql
    assert '"VERPR"' in sql
    assert "*" in sql
