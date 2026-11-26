"""V4 ageing buckets equal independent SQL, agree with the dormant analysis, and respect scope and cost rights."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from lumiant.analyses import cache
from lumiant.analyses.ageing import run_ageing
from lumiant.analyses.risks import run_dormant
from lumiant.auth.principal import Principal
from lumiant.query.service import QueryService
from tests.helpers import raw_duckdb

pytestmark = pytest.mark.integration


def independent(alpha_db: Path, as_of: str) -> dict[str, tuple[int, Decimal]]:
    con = raw_duckdb(alpha_db)
    rows = con.execute(
        """
        WITH onhand AS (SELECT MATNR, WERKS, sum(LABST) q, sum(LABST * VERPR) v FROM ZV_STOCK GROUP BY 1, 2 HAVING sum(LABST) > 0),
             last AS (SELECT MATNR, WERKS, max(BUDAT) d FROM ZV_MOVEMENT WHERE BWART = 'ISSUE' GROUP BY 1, 2)
        SELECT CASE WHEN l.d IS NULL THEN 'never'
                    WHEN l.d >= ?::DATE - INTERVAL 90 DAY THEN '0-90'
                    WHEN l.d >= ?::DATE - INTERVAL 180 DAY THEN '91-180'
                    WHEN l.d >= ?::DATE - INTERVAL 365 DAY THEN '181-365' ELSE '365+' END b,
               count(*), sum(o.v)
        FROM onhand o LEFT JOIN last l USING (MATNR, WERKS) GROUP BY 1
        """,
        [as_of, as_of, as_of],
    ).fetchall()
    con.close()
    return {str(b): (int(n), Decimal(v or 0).quantize(Decimal("0.01"))) for b, n, v in rows}


def test_ageing_matches_independent_sql(
    query_service: QueryService, principals: dict[str, Principal], alpha_db: Path
) -> None:
    cache.clear(query_service)
    result = run_ageing(query_service, principals["alpha.admin"])
    truth = independent(alpha_db, result["as_of"])
    for b in result["buckets"]:
        n, v = truth.get(b["bucket"], (0, Decimal("0.00")))
        assert b["pairs"] == n, b["bucket"]
        if n:
            assert Decimal(b["value"]["USD"]) == v, b["bucket"]


def test_ageing_agrees_with_dormant(query_service: QueryService, principals: dict[str, Principal]) -> None:
    result = run_ageing(query_service, principals["alpha.admin"])
    by = {b["bucket"]: b["pairs"] for b in result["buckets"]}
    dormant = run_dormant(query_service, principals["alpha.admin"], days=365, limit=1, offset=0)
    # Dormant 365 = no issue in the last 365 days, or never: the "365+" and "never" buckets. The bucket boundary is
    # inclusive (>= as_of - 365) while dormant uses a strict cutoff, so they agree exactly only away from that day.
    assert abs((by["365+"] + by["never"]) - int((dormant.summary or {})["flagged"])) <= 1


def test_ageing_hides_value_without_cost_and_applies_scope(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    analyst = run_ageing(query_service, principals["alpha.analyst"])
    admin = run_ageing(query_service, principals["alpha.admin"])
    assert analyst["value_visible"] is False
    assert all("value" not in b for b in analyst["buckets"])
    assert sum(b["pairs"] for b in analyst["buckets"]) < sum(b["pairs"] for b in admin["buckets"])
