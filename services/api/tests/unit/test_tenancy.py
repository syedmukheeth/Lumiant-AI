from pathlib import Path

import pytest
import yaml

from lumiant.core.config import BASE_DIR
from lumiant.tenancy.registry import TenantConfigError, TenantRegistry, parse_tenant_file

TENANT_DIR = BASE_DIR / "config" / "tenants"


def load_raw(name: str) -> dict[str, object]:
    raw = yaml.safe_load((TENANT_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    return raw


def write(tmp_path: Path, raw: dict[str, object], name: str = "t.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return path


def test_demo_tenants_load() -> None:
    reg = TenantRegistry.load(TENANT_DIR)
    assert set(reg.ids()) == {"demo-alpha", "demo-beta"}
    alpha = reg.get("demo-alpha")
    assert alpha.synthetic
    assert alpha.warehouses_of_departments(["NORTH"]) == {"1100", "1110", "1120"}


def test_find_dev_user_across_tenants() -> None:
    reg = TenantRegistry.load(TENANT_DIR)
    found = reg.find_dev_user("beta.user")
    assert found is not None
    tenant, user = found
    assert tenant.id == "demo-beta"
    assert user.warehouses == ["LDS1"]
    assert reg.find_dev_user("nobody") is None


def test_unknown_key_rejected(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["surprise"] = True
    with pytest.raises(TenantConfigError, match="surprise"):
        parse_tenant_file(write(tmp_path, raw))


def test_unknown_canonical_field_rejected(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["datasets"]["stock_balance"]["fields"]["guessed_field"] = "XYZ"  # type: ignore[index]
    with pytest.raises(TenantConfigError, match="guessed_field"):
        parse_tenant_file(write(tmp_path, raw))


def test_required_field_must_be_mapped(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    del raw["datasets"]["stock_balance"]["fields"]["quantity"]  # type: ignore[index]
    with pytest.raises(TenantConfigError, match="required field 'quantity'"):
        parse_tenant_file(write(tmp_path, raw))


def test_computed_field_cannot_be_mapped(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["datasets"]["stock_balance"]["fields"]["stock_value"] = "WERT"  # type: ignore[index]
    with pytest.raises(TenantConfigError, match="computed"):
        parse_tenant_file(write(tmp_path, raw))


@pytest.mark.security
def test_physical_identifiers_must_be_plain(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["datasets"]["stock_balance"]["source"] = "ZV_STOCK; DROP TABLE x"  # type: ignore[index]
    with pytest.raises(TenantConfigError):
        parse_tenant_file(write(tmp_path, raw))


@pytest.mark.security
@pytest.mark.parametrize("path", ["../outside.duckdb", "C:/abs.duckdb", "/abs.duckdb"])
def test_connection_path_must_stay_inside(tmp_path: Path, path: str) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["connection"]["path"] = path  # type: ignore[index]
    with pytest.raises(TenantConfigError, match="path"):
        parse_tenant_file(write(tmp_path, raw))


def test_dev_user_must_reference_known_role_and_scope(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["dev_users"] = [{"username": "x.user", "display_name": "X", "roles": ["ghost"], "warehouses": ["9999"]}]
    with pytest.raises(TenantConfigError) as exc:
        parse_tenant_file(write(tmp_path, raw))
    assert any("unknown role" in p for p in exc.value.problems)
    assert any("unknown warehouse" in p for p in exc.value.problems)


@pytest.mark.security
def test_customer_tenants_cannot_have_dev_users(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["data_classification"] = "customer"
    with pytest.raises(TenantConfigError, match="dev_users are not allowed"):
        parse_tenant_file(write(tmp_path, raw))


def test_unknown_permission_rejected(tmp_path: Path) -> None:
    raw = load_raw("demo-alpha.yaml")
    raw["roles"]["standard_user"] = ["inventory:read", "everything:write"]  # type: ignore[index]
    with pytest.raises(TenantConfigError):
        parse_tenant_file(write(tmp_path, raw))


def test_duplicate_dev_username_across_tenants_rejected(tmp_path: Path) -> None:
    alpha = load_raw("demo-alpha.yaml")
    beta = load_raw("demo-beta.yaml")
    beta["dev_users"][0]["username"] = "alpha.admin"  # type: ignore[index]
    write(tmp_path, alpha, "a.yaml")
    write(tmp_path, beta, "b.yaml")
    with pytest.raises(TenantConfigError, match="also defined"):
        TenantRegistry.load(tmp_path)
