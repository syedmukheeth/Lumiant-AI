"""V4: the inventory value trend equals independent SQL, its current point equals today's value, and scope applies."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from lumiant.analyses import cache
from lumiant.analyses.trends import month_ends, run_value_trend
from lumiant.auth.principal import Principal
from lumiant.core.errors import ForbiddenError
from lumiant.metrics.service import MetricsService
from lumiant.query.service import QueryService
from tests.helpers import raw_duckdb

pytestmark = pytest.mark.integration


def test_month_ends() -> None:
    assert month_ends(date(2026, 3, 10), 3) == [
        date(2025, 12, 31),
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 10),
    ]


def independent(alpha_db: Path, end: str) -> tuple[Decimal, Decimal, Decimal]:
    """(value at month end, receipts value, issues value) from raw SQL on the source tables."""
    con = raw_duckdb(alpha_db)
    value = con.execute(
        """
        WITH onhand AS (SELECT MATNR, WERKS, sum(LABST) q, max(VERPR) p FROM ZV_STOCK WHERE VERPR IS NOT NULL GROUP BY 1, 2),
             later AS (SELECT MATNR, WERKS, sum(MENGE) a FROM ZV_MOVEMENT WHERE BUDAT > ?::DATE GROUP BY 1, 2)
        SELECT sum((o.q - coalesce(l.a, 0)) * o.p) FROM onhand o LEFT JOIN later l USING (MATNR, WERKS)
        """,
        [end],
    ).fetchone()
    con.close()
    assert value is not None
    return Decimal(value[0]).quantize(Decimal("0.01")), Decimal(0), Decimal(0)


def test_value_trend_matches_independent_sql(
    query_service: QueryService, principals: dict[str, Principal], alpha_db: Path
) -> None:
    cache.clear(query_service)
    result = run_value_trend(query_service, principals["alpha.admin"], months=6)
    [series] = result["series"]
    assert series["currency"] == "USD"
    assert len(series["points"]) == 7
    for point in series["points"]:
        expected, _, _ = independent(alpha_db, point["date"])
        assert Decimal(point["value"]) == expected, point["period"]
    assert series["points"][-1]["period"] == "now"
    assert all(p["receipts_value"] is not None for p in series["points"][1:])


def test_current_point_equals_todays_value(query_service: QueryService, principals: dict[str, Principal]) -> None:
    result = run_value_trend(query_service, principals["alpha.admin"], months=3)
    now = Decimal(result["series"][0]["points"][-1]["value"])
    _, total = MetricsService(query_service).run("inventory_value_total", principals["alpha.admin"])
    assert now == Decimal(str(total.rows[0]["value"])).quantize(Decimal("0.01"))


def test_value_trend_respects_scope_and_cost_rights(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    everyone = run_value_trend(query_service, principals["alpha.admin"], months=3)
    north = run_value_trend(query_service, principals["alpha.north_manager"], months=3)
    assert Decimal(north["series"][0]["points"][-1]["value"]) < Decimal(everyone["series"][0]["points"][-1]["value"])
    with pytest.raises(ForbiddenError):
        run_value_trend(query_service, principals["alpha.analyst"], months=3)
