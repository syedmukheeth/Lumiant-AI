import sqlalchemy as sa

from lumiant.core.config import BASE_DIR
from lumiant.mapping.resolver import SourceObject, TenantMapping
from lumiant.tenancy.registry import TenantRegistry

REG = TenantRegistry.load(BASE_DIR / "config" / "tenants")
ALPHA = TenantMapping(REG.get("demo-alpha"))
BETA = TenantMapping(REG.get("demo-beta"))
GAMMA = TenantMapping(REG.get("demo-gamma"))


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


def test_value_map_compiles_to_case_with_inline_constants() -> None:
    t = GAMMA.table("item").alias("b")
    sql = str(
        sa.select(GAMMA.column_expr("item", "inventory_stage", t)).compile(compile_kwargs={"render_postcompile": True})
    )
    assert "CASE WHEN (b.material_type IS NULL) THEN NULL" in sql
    assert "WHEN (b.material_type = 'ROH') THEN 'RAW'" in sql
    assert "ELSE 'unmapped' END" in sql
    assert GAMMA.physical_ref("item", "inventory_stage") == "value_map(v_item.material_type)"
    # The raw code stays available as an attribute.
    assert GAMMA.physical_ref("item", "attr_material_type") == "v_item.material_type"


def test_has_ref_follows_joins_and_mapping() -> None:
    assert GAMMA.has_ref("stock_balance", "item.item_group")
    assert GAMMA.has_ref("stock_balance", "item_warehouse.abc_class")
    assert not GAMMA.has_ref("stock_balance", "lot_id")
    assert not GAMMA.has_ref("stock_balance", "warehouse.name")
    assert not GAMMA.has_ref("stock_balance", "lot.expiry_date")
    assert not ALPHA.has_ref("stock_balance", "item_warehouse.abc_class")
    assert ALPHA.has_ref("stock_balance", "lot.expiry_date")
