"""Planning on the synthetic manufacturing tenant (demo-delta): canonical data → query engine → loader → engine →
API and assistant, with scope, cost permissions and grounding. Engine correctness itself is covered by the scenario
harness (tests/unit/test_planning_scenarios.py); these tests prove the wiring and the security rails."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lumiant.agent.service import AgentService
from lumiant.auth.principal import Principal
from lumiant.core.config import Settings
from lumiant.core.errors import AppError
from lumiant.main import create_app
from lumiant.planning.service import PlanningService
from lumiant.query.service import QueryService
from tests.conftest import AS_OF
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


@pytest.fixture(scope="module")
def svc(query_service: QueryService) -> PlanningService:
    return PlanningService(query_service)


@pytest.fixture(scope="module")
def agent(query_service: QueryService) -> AgentService:
    return AgentService(query_service, Settings(_env_file=None))  # type: ignore[call-arg]


def test_fulfilment_traces_late_pump_order_to_the_impeller(
    svc: PlanningService, principals: dict[str, Principal]
) -> None:
    out = svc.fulfilment(principals["delta.admin"], today=AS_OF)
    lines = {ln["key"]: ln for ln in out["lines"]}
    pump = lines["SO-1001/10"]
    assert pump["from_stock"] == "12"  # 12 usable; 3 in inspection and 2 returned are not counted
    assert pump["on_time"] is False
    assert any("RM-IMPELLER" in r for r in pump["reasons"])
    assert lines["SO-1003/10"]["on_time"] is True
    assert out["recommendation_only"] is True


def test_material_plan_uses_plant_procurement_and_reports_missing_lead_time(
    svc: PlanningService, principals: dict[str, Principal]
) -> None:
    out = svc.material_plan(principals["delta.admin"], today=AS_OF)
    rows = out["planned_orders"]
    jed = [r for r in rows if r["item_id"] == "FG-VALVE-50" and r["warehouse_id"] == "JED1"]
    assert jed
    assert jed[0]["action"] == "buy"  # bought in by the distribution centre
    assert {r["action"] for r in rows if r["item_id"] == "FG-VALVE-50" and r["warehouse_id"] == "RYD1"} == {"make"}
    assert not [r for r in rows if r["item_id"] == "PH-KIT-01"]  # phantom never planned
    copper = [r for r in rows if r["item_id"] == "RM-COPPER"]
    assert copper
    assert copper[0]["release"] is None
    assert any("not maintained" in m for m in copper[0]["issues"])


def test_supplier_comparison_respects_eligibility_and_policy(
    svc: PlanningService, principals: dict[str, Principal]
) -> None:
    from datetime import timedelta

    need = AS_OF + timedelta(days=31)
    out = svc.suppliers(
        principals["delta.admin"], "RM-IMPELLER", Decimal(27), need_date=need, policy="balanced", today=AS_OF
    )
    offers = {o["supplier_id"]: o for o in out["offers"]}
    assert offers["SUP-BETA"]["rank"] == 1
    assert offers["SUP-ALPHA"]["eligible"] is True
    assert "expired" in offers["SUP-OMEGA"]["reasons"][0]
    assert "not approved" in offers["SUP-ZETA"]["reasons"][0]
    assert "exchange rate" in offers["SUP-GAMMA"]["reasons"][0]  # USD quote: no approved rate, not compared
    urgent = svc.suppliers(
        principals["delta.admin"],
        "RM-IMPELLER",
        Decimal(27),
        need_date=AS_OF + timedelta(days=14),
        policy="urgent",
        today=AS_OF,
    )
    assert next(o for o in urgent["offers"] if o["supplier_id"] == "SUP-ALPHA")["eligible"] is False
    assert "no purchase order is created" in urgent["recommendation"]


def test_supplier_prices_need_cost_access(svc: PlanningService, principals: dict[str, Principal]) -> None:
    with pytest.raises(AppError) as exc:
        svc.suppliers(principals["delta.planner"], "RM-IMPELLER", Decimal(5), need_date=None)
    assert exc.value.status_code == 403


def test_planner_sees_only_their_warehouse(svc: PlanningService, principals: dict[str, Principal]) -> None:
    out = svc.fulfilment(principals["delta.planner"], today=AS_OF)
    assert {ln["warehouse_id"] for ln in out["lines"]} == {"RYD1"}
    assert "SO-1005/10" not in {ln["key"] for ln in out["lines"]}  # Jeddah order is out of scope


def test_bom_duplicates_and_lifecycle(svc: PlanningService, principals: dict[str, Principal]) -> None:
    bom = svc.bom(principals["delta.admin"], "FG-SKID-1", Decimal(2), AS_OF)
    assert bom["totals"]["RM-BOLT-M10"] == "16"  # via the phantom kit inside the pump
    assert "PH-KIT-01" not in bom["totals"]
    dups = svc.duplicates(principals["delta.admin"])["findings"]
    assert any({f["item_a"], f["item_b"]} == {"RM-BOLT-M10", "RM-BOLT-M10B"} for f in dups)
    life = {f["item_id"]: f["verdict"] for f in svc.lifecycle(principals["delta.admin"], AS_OF)["findings"]}
    assert life["SP-BEARING-7310"] == "critical_keep"
    assert life["SP-GASKET-OLD"] == "obsolete_candidate"
    assert life["RM-STEEL-S1"] == "superseded_run_down"


def test_other_tenants_are_untouched(svc: PlanningService, principals: dict[str, Principal]) -> None:
    with pytest.raises(AppError) as exc:
        svc.fulfilment(principals["alpha.admin"])
    assert exc.value.status_code == 409  # alpha has no customer orders mapped


@pytest.mark.parametrize(
    ("question", "tool"),
    [
        ("Can we fulfil our open orders?", "order_fulfilment"),
        ("Will order SO-1001 be late?", "order_fulfilment"),
        ("What raw materials should we buy?", "material_plan"),
        ("Show the bill of materials for FG-SKID-1", "bom_explosion"),
        ("Compare suppliers for 27 units of RM-IMPELLER", "supplier_comparison"),
        ("Find duplicate item codes", "duplicate_items"),
        ("Which items are obsolete?", "lifecycle_review"),
        ("Do we have enough machine capacity next month?", "planning_scope"),
    ],
)
def test_assistant_routes_planning_questions(
    agent: AgentService, principals: dict[str, Principal], question: str, tool: str
) -> None:
    out = agent.chat(principals["delta.admin"], question)
    assert [c["name"] for c in out["tool_calls"]] == [tool], out["answer"]
    assert out["grounding"]["passed"], out["grounding"]
    assert out["answer"]


def test_assistant_supplier_question_without_cost_access_is_refused(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["delta.planner"], "Compare suppliers for 27 units of RM-IMPELLER")
    assert out["kind"] == "unsupported"
    assert "SAR" not in json.dumps(out, default=str)


def test_planning_api_scope_and_permissions(data_dir: Any, tmp_path_factory: pytest.TempPathFactory) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="planning-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("planningdb") / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/dev-login", json={"username": "delta.planner"}, headers=CSRF)
        r = c.get(f"/api/planning/fulfilment?as_of={AS_OF.isoformat()}", headers=CSRF)
        assert r.status_code == 200
        assert {ln["warehouse_id"] for ln in r.json()["lines"]} == {"RYD1"}
        assert c.get("/api/planning/suppliers?item=RM-IMPELLER&qty=5", headers=CSRF).status_code == 403
        assert c.post(
            "/api/planning/assess", json={"question": "Can our capacity handle Ramadan demand?"}
        ).status_code in (401, 403)
        r = c.post("/api/planning/assess", json={"question": "Can our capacity handle Ramadan demand?"}, headers=CSRF)
        assert r.status_code == 200
        assert r.json()["mode"] == "unsupported"
