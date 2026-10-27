"""OIDC bearer authentication, verified with locally generated keys and a fake JWKS client (no real IdP: Q-010)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import lumiant.auth.oidc as oidc_module
from lumiant.core.config import BASE_DIR, Settings
from lumiant.main import create_app
from lumiant.tenancy.registry import TenantConfigError, TenantRegistry, parse_tenant_file

ISSUER = "https://idp.example.test/realms/alpha"
AUDIENCE = "lumiant-alpha"
CSRF = {"X-Requested-With": "lumiant"}


def make_key() -> Any:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


KEY, OTHER_KEY = make_key(), make_key()


class FakeJwks:
    def __init__(self, public_key: Any) -> None:
        self._key = public_key

    def get_signing_key_from_jwt(self, token: str) -> Any:
        return SimpleNamespace(key=self._key)


def token(*, key: Any = KEY, alg: str = "RS256", **overrides: Any) -> str:
    now = int(time.time())
    claims: dict[str, Any] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "u-123",
        "iat": now,
        "exp": now + 600,
        "preferred_username": "nora.north",
        "name": "Nora North",
        "groups": ["lumiant-north-managers"],
    }
    claims.update(overrides)
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm=alg)


@pytest.fixture(scope="module")
def tenant_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("oidc-tenants")
    for name in ("demo-alpha", "demo-beta"):
        raw = yaml.safe_load((BASE_DIR / "config" / "tenants" / f"{name}.yaml").read_text(encoding="utf-8"))
        if name == "demo-alpha":
            raw["oidc"] = {
                "issuer": ISSUER,
                "audience": AUDIENCE,
                "jwks_url": "https://idp.example.test/jwks",
                "group_roles": {
                    "lumiant-admins": "super_admin",
                    "lumiant-north-managers": "dept_admin",
                    "lumiant-viewers": "viewer_no_cost",
                },
                "group_scopes": {
                    "lumiant-admins": {"warehouses": ["*"]},
                    "lumiant-north-managers": {"departments": ["NORTH"]},
                    "lumiant-viewers": {"warehouses": ["3100"]},
                },
            }
        (root / f"{name}.yaml").write_text(yaml.safe_dump(raw), encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def client(tenant_dir: Path, data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    mp = pytest.MonkeyPatch()
    mp.setattr(oidc_module, "_default_jwks_client", lambda url: FakeJwks(KEY.public_key()))
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="oidc",
        tenant_config_dir=tenant_dir,
        data_dir=data_dir,
        app_db_url=f"sqlite:///{(tmp_path_factory.mktemp('oidcdb') / 'app.db').as_posix()}",
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        yield c
    mp.undo()


def me(client: TestClient, tok: str | None) -> Any:
    return client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"} if tok else {})


def test_valid_token_maps_groups_to_roles_and_scope(client: TestClient) -> None:
    r = me(client, token())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tenant"]["id"] == "demo-alpha"
    assert body["user"] == {"id": "nora.north", "display_name": "Nora North"}
    assert body["roles"] == ["dept_admin"]
    assert body["scope"]["warehouses"] == ["1100", "1110", "1120"]
    assert "cost:read" in body["permissions"]
    assert body["auth_mode"] == "oidc"


def test_multiple_groups_union_roles_and_scope(client: TestClient) -> None:
    body = me(client, token(groups=["lumiant-viewers", "lumiant-north-managers"])).json()
    assert set(body["roles"]) == {"viewer_no_cost", "dept_admin"}
    assert set(body["scope"]["warehouses"]) == {"1100", "1110", "1120", "3100"}
    admin = me(client, token(groups=["lumiant-admins"])).json()
    assert admin["scope"]["all_warehouses"] is True
    assert "admin:tenant" in admin["permissions"]


def test_data_requests_use_the_mapped_scope(client: TestClient) -> None:
    h = {"Authorization": f"Bearer {token(groups=['lumiant-viewers'])}"}
    rows = client.get("/api/inventory/balances", params={"limit": 200}, headers=h).json()["data"]
    assert rows
    assert {r["warehouse_id"] for r in rows} == {"3100"}
    assert not {"valuation_price", "stock_value"} & set(rows[0])  # viewer role has no cost access
    assert client.get("/api/inventory/balances", params={"warehouse": "1100"}, headers=h).status_code == 403


@pytest.mark.security
@pytest.mark.parametrize(
    ("label", "tok"),
    [
        ("expired", token(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200)),
        ("wrong audience", token(aud="someone-else")),
        ("unknown issuer", token(iss="https://evil.example.test")),
        ("signed by another key", token(key=OTHER_KEY)),
        (
            "alg none",
            jwt.encode(
                {"iss": ISSUER, "aud": AUDIENCE, "sub": "x", "exp": int(time.time()) + 600}, key=None, algorithm="none"
            ),
        ),
        ("missing subject", token(sub=None)),
        ("garbage", "not.a.jwt"),
    ],
)
def test_bad_tokens_are_rejected(client: TestClient, label: str, tok: str) -> None:
    r = me(client, tok)
    assert r.status_code == 401, label
    assert r.json()["error"]["code"] == "not_authenticated"
    assert "signature" not in r.text.lower()  # no verification detail leaks


def _forge_hs256(secret: bytes) -> str:
    """Hand-built HS256 token: PyJWT refuses to sign with a PEM key, an attacker would not."""

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = b64(
        json.dumps(
            {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "sub": "attacker",
                "exp": int(time.time()) + 600,
                "groups": ["lumiant-admins"],
            }
        ).encode()
    )
    sig = hmac.new(secret, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{b64(sig)}"


@pytest.mark.security
def test_hmac_key_confusion_attack_is_rejected(client: TestClient) -> None:
    public_pem = KEY.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    assert me(client, _forge_hs256(public_pem)).status_code == 401


@pytest.mark.security
def test_user_without_a_mapped_group_gets_no_access(client: TestClient) -> None:
    for groups in ([], ["some-other-group"], None):
        r = me(client, token(groups=groups))
        assert r.status_code == 403, groups
        assert r.json()["error"]["code"] == "no_access"


@pytest.mark.security
def test_cookies_and_missing_headers_do_not_authenticate_in_oidc_mode(client: TestClient) -> None:
    assert me(client, None).status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401
    assert client.get("/api/auth/dev-users").status_code == 404
    assert client.post("/api/auth/dev-login", json={"username": "alpha.admin"}, headers=CSRF).status_code == 404


def test_jwks_failure_is_not_a_server_error(tenant_dir: Path, data_dir: Path, tmp_path: Path) -> None:
    class Broken:
        def get_signing_key_from_jwt(self, token: str) -> Any:
            raise OSError("idp unreachable at 10.0.0.5")

    mp = pytest.MonkeyPatch()
    mp.setattr(oidc_module, "_default_jwks_client", lambda url: Broken())
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="oidc",
        tenant_config_dir=tenant_dir,
        data_dir=data_dir,
        app_db_url=f"sqlite:///{(tmp_path / 'a.db').as_posix()}",
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        r = c.get("/api/auth/me", headers={"Authorization": f"Bearer {token()}"})
    mp.undo()
    assert r.status_code == 401
    assert "10.0.0.5" not in r.text


def test_oidc_config_is_validated(tmp_path: Path) -> None:
    raw = yaml.safe_load((BASE_DIR / "config" / "tenants" / "demo-alpha.yaml").read_text(encoding="utf-8"))
    raw["oidc"] = {
        "issuer": "http://insecure.test",
        "audience": "a",
        "jwks_url": "https://x.test/jwks",
        "group_roles": {"g": "super_admin"},
    }
    path = tmp_path / "t.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(TenantConfigError):
        parse_tenant_file(path)  # issuer must be https
    raw["oidc"]["issuer"] = "https://ok.test"
    raw["oidc"]["group_roles"] = {"g": "ghost_role"}
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(TenantConfigError, match="unknown role"):
        parse_tenant_file(path)
    raw["oidc"]["group_roles"] = {"g": "super_admin"}
    raw["oidc"]["group_scopes"] = {"g": {"warehouses": ["9999"]}}
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(TenantConfigError, match="unknown warehouse"):
        parse_tenant_file(path)


def test_oidc_mode_requires_a_configured_tenant(data_dir: Path, tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="oidc",
        data_dir=data_dir,
        app_db_url=f"sqlite:///{(tmp_path / 'b.db').as_posix()}",
        log_level="WARNING",
    )
    with pytest.raises(RuntimeError, match="needs at least one tenant"):
        create_app(settings)
    assert TenantRegistry.load(BASE_DIR / "config" / "tenants")
