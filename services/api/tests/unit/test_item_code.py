import pytest

from lumiant.core.config import BASE_DIR
from lumiant.costing.item_code import parse_item_code
from lumiant.tenancy.registry import TenantRegistry

REG = TenantRegistry.load(BASE_DIR / "config" / "tenants")
ALPHA = REG.get("demo-alpha").item_coding
BETA = REG.get("demo-beta").item_coding


def test_alpha_segments_are_configuration_not_assumption() -> None:
    assert ALPHA is not None
    p = parse_item_code("1105000021", ALPHA)
    assert p.valid
    assert p.segments == {"category": "11", "material": "05", "serial": "000021"}


def test_beta_uses_a_different_scheme_for_the_same_engine() -> None:
    assert BETA is not None
    assert parse_item_code("RB-0012-B", BETA).segments == {"group_prefix": "RB", "serial": "0012", "variant": "B"}
    bad = parse_item_code("RB-0012-Z", BETA)
    assert not bad.valid
    assert "pattern_mismatch" in bad.problems


@pytest.mark.parametrize("code", ["", None, "123", "11050000AB", "11050000211"])
def test_invalid_alpha_codes(code: str | None) -> None:
    assert ALPHA is not None
    assert not parse_item_code(code, ALPHA).valid
