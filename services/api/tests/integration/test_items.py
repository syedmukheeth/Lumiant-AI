"""V4 Material 360: one item's sections are scoped, hide cost without cost rights, and match the source."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lumiant.core.config import Settings
from lumiant.main import create_app
from tests.helpers import app_db_url, raw_duckdb

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


@pytest.fixture(scope="module")
def client(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="items-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("itemsdb") / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client: TestClient, user: str) -> None:
    client.cookies.clear()
    assert client.post("/api/auth/dev-login", json={"username": user}, headers=CSRF).status_code == 200


def busiest(alpha_db: Path) -> tuple[str, Decimal, int]:
    con = raw_duckdb(alpha_db)
    row = con.execute(
        "SELECT MATNR, sum(LABST), count(DISTINCT WERKS) FROM ZV_STOCK GROUP BY 1 ORDER BY 3 DESC, 1 LIMIT 1"
    ).fetchone()
    con.close()
    assert row is not None
    return str(row[0]), Decimal(row[1]), int(row[2])


def test_item_360_matches_the_source(client: TestClient, alpha_db: Path) -> None:
    item, qty, warehouses = busiest(alpha_db)
    login(client, "alpha.admin")
    body = client.get(f"/api/items/{item}").json()
    assert body["master"]["rows"][0]["item_id"] == item
    stock = body["stock"]["rows"]
    assert len(stock) == warehouses
    assert sum(Decimal(r["quantity"]) for r in stock) == qty
    assert all("value" in r for r in stock)
    assert body["movements"]["available"] is True
    dates = [r["posting_date"] for r in body["movements"]["rows"]]
    assert dates == sorted(dates, reverse=True)


def test_item_360_respects_scope_and_cost(client: TestClient, alpha_db: Path) -> None:
    item, _, _ = busiest(alpha_db)
    login(client, "alpha.analyst")  # warehouse 3100 only, no cost access
    body = client.get(f"/api/items/{item}").json()
    assert all(r["warehouse_id"] == "3100" for r in body["stock"]["rows"])
    assert all("value" not in r for r in body["stock"]["rows"])
    assert body["cost_visible"] is False


def test_unknown_item_is_404(client: TestClient) -> None:
    login(client, "alpha.admin")
    assert client.get("/api/items/NO-SUCH-ITEM").status_code == 404
