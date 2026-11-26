"""V3: API keys for service accounts and the MCP server. A key never does more than its creator, works without a
browser session, can be revoked, and lets an AI assistant use Lumiant's typed tools within the key's scope."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lumiant.core.config import Settings
from lumiant.main import create_app
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


@pytest.fixture(scope="module")
def client(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="keys-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("keysdb") / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client: TestClient, username: str) -> None:
    client.cookies.clear()
    assert client.post("/api/auth/dev-login", json={"username": username}, headers=CSRF).status_code == 200


def new_key(client: TestClient, **body: Any) -> str:
    login(client, "alpha.admin")
    r = client.post("/api/admin/api-keys", json={"name": "test", **body}, headers=CSRF)
    assert r.status_code == 200, r.text
    client.cookies.clear()
    return str(r.json()["key"])


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_a_key_reads_within_its_rights_and_scope(client: TestClient) -> None:
    key = new_key(client, permissions=["dashboard:read", "inventory:read"], warehouses=["3100"])
    items = client.get("/api/metrics/items_in_stock", headers=bearer(key))
    assert items.status_code == 200
    injected = items.json()["provenance"]["filters"]["injected"]
    assert injected
    assert injected[0]["value"] == ["3100"]
    assert client.get("/api/metrics/inventory_value_total", headers=bearer(key)).status_code == 403  # no cost:read
    assert client.get("/api/admin/source", headers=bearer(key)).status_code == 403  # never admin
    assert client.get("/api/metrics/items_in_stock").status_code == 401  # no key, no session


def test_a_key_cannot_exceed_its_creator(client: TestClient) -> None:
    login(client, "alpha.admin")
    r = client.post("/api/admin/api-keys", json={"name": "x", "permissions": ["admin:tenant"]}, headers=CSRF)
    assert r.status_code == 403
    login(client, "alpha.north_manager")
    r = client.post(
        "/api/admin/api-keys",
        json={"name": "x", "permissions": ["inventory:read"], "warehouses": ["3100"]},
        headers=CSRF,
    )
    assert r.status_code == 403  # dept admin has no admin:tenant at all


def test_keys_are_stored_hashed_listed_and_revocable(client: TestClient) -> None:
    key = new_key(client, permissions=["inventory:read", "dashboard:read"])
    key_id = key.removeprefix("lmk_").split("_")[0]
    login(client, "alpha.admin")
    listed = client.get("/api/admin/api-keys").json()["keys"]
    assert any(k["id"] == key_id for k in listed)
    assert key.split("_", 2)[2] not in str(listed), "the secret is never listed"
    assert client.delete(f"/api/admin/api-keys/{key_id}", headers=CSRF).status_code == 200
    client.cookies.clear()
    assert client.get("/api/metrics/items_in_stock", headers=bearer(key)).status_code == 401
    assert client.get("/api/metrics/items_in_stock", headers=bearer("lmk_000000000000_forged")).status_code == 401


def test_a_key_needs_no_csrf_header(client: TestClient) -> None:
    key = new_key(client, permissions=["inventory:read", "query:run"])
    plan = {"dataset": "stock_balance", "measures": [{"field": "item_id", "agg": "count", "alias": "n"}]}
    r = client.post("/api/query", json=plan, headers=bearer(key))
    assert r.status_code == 200, r.text


# ------------------------------------------------------------------------------------------------ MCP
def rpc(client: TestClient, key: str, method: str, params: dict[str, Any] | None = None, msg_id: int | None = 1) -> Any:
    msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if msg_id is not None:
        msg["id"] = msg_id
    return client.post("/mcp", json=msg, headers=bearer(key))


def test_mcp_handshake_and_tools(client: TestClient) -> None:
    key = new_key(client, permissions=["dashboard:read", "inventory:read", "chat:use"])
    init = rpc(
        client, key, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}
    )
    assert init.json()["result"]["protocolVersion"] == "2025-06-18"
    assert init.json()["result"]["capabilities"]["tools"] == {"listChanged": False}
    assert rpc(client, key, "notifications/initialized", msg_id=None).status_code == 202
    names = {t["name"] for t in rpc(client, key, "tools/list").json()["result"]["tools"]}
    assert {"inventory_summary", "ask_lumiant", "expiring_lots"} <= names
    assert all(t["annotations"]["readOnlyHint"] for t in rpc(client, key, "tools/list").json()["result"]["tools"])


def test_mcp_tool_returns_the_platform_figure(client: TestClient) -> None:
    key = new_key(client, permissions=["dashboard:read", "inventory:read", "chat:use"])
    result = rpc(client, key, "tools/call", {"name": "inventory_summary", "arguments": {}}).json()["result"]
    assert result["isError"] is False
    lines = client.get("/api/metrics/stock_lines", headers=bearer(key)).json()["data"][0]["lines"]
    assert f"{int(lines):,}" in result["content"][0]["text"]
    assert result["structuredContent"]["provenance"]["tenant_id"] == "demo-alpha"


def test_mcp_refuses_safely(client: TestClient) -> None:
    key = new_key(client, permissions=["dashboard:read", "inventory:read"])
    unknown = rpc(client, key, "tools/call", {"name": "drop_tables", "arguments": {}}).json()
    assert unknown["error"]["code"] == -32602
    assert rpc(client, key, "resources/list").json()["error"]["code"] == -32601
    assert client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).status_code == 401
    bad = rpc(client, key, "tools/call", {"name": "expiring_lots", "arguments": {"days": "lots"}}).json()["result"]
    assert bad["isError"] is True


def test_mcp_ask_answers_in_plain_language(client: TestClient) -> None:
    key = new_key(client, permissions=["dashboard:read", "inventory:read", "chat:use"])
    result = rpc(
        client, key, "tools/call", {"name": "ask_lumiant", "arguments": {"question": "How many items do we have?"}}
    )
    body = result.json()["result"]
    assert body["isError"] is False
    assert body["structuredContent"]["tool_calls"]
