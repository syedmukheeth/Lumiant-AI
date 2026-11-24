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
    with pytest.raises(AppError) as exc:
        svc.lifecycle(principals["alpha.admin"])
    assert exc.value.status_code == 409  # no criticality data: never judge obsolescence from inactivity alone


def test_planning_sections_follow_role_and_tenant_data(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    from types import SimpleNamespace

    from lumiant.api.auth import planning_sections

    container = SimpleNamespace(query=query_service)
    assert planning_sections(principals["delta.admin"], container) == ["planning", "procurement", "master_data"]  # type: ignore[arg-type]
    assert planning_sections(principals["delta.planner"], container) == ["planning", "master_data"]  # type: ignore[arg-type]
    assert planning_sections(principals["alpha.admin"], container) == ["master_data"]  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("question", "tool"),
    [
        ("Can we fulfil our open orders?", "order_fulfilment"),
        ("Will order SO-1001 be late?", "order_fulfilment"),
        ("What raw materials should we buy?", "material_plan"),
        ("Show the bill of materials for FG-SKID-1", "bom_explosion"),
        ("Compare suppliers for 27 units of RM-IMPELLER", "supplier_comparison"),
        ("Is it worth paying more to protect order SO-1001?", "customer_commitment"),
        ("Which customer commitments are at risk?", "customer_commitment"),
        # Everyday wording (natural-language regression set)
        ("Can we still deliver SO-1001 on time if we use a faster supplier?", "customer_commitment"),
        ("Which orders are we going to miss and how much money is at stake?", "customer_commitment"),
        ("How do we save the CUST-OASIS order?", "customer_commitment"),
        ("What happens if we buy from the expensive supplier to make the deadline?", "customer_commitment"),
        ("how much revenue is at risk from late orders", "customer_commitment"),
        ("Which supplier gets SO-1001 out the door in time?", "customer_commitment"),
        ("Is there any way to hit the customer date for SO-1005?", "customer_commitment"),
        ("cheaper supplier or faster supplier for the pump order?", "customer_commitment"),
        ("What will it cost us to avoid late penalties?", "customer_commitment"),
        ("Can we split the impeller order between suppliers to meet the date?", "customer_commitment"),
        ("Are any customer orders going to be late?", "order_fulfilment"),
        ("When will SO-1001 ship?", "order_fulfilment"),
        ("What do I need to order this week?", "material_plan"),
        ("What are we short of?", "material_plan"),
        ("Who's the best supplier for RM-IMPELLER, I need 27?", "supplier_comparison"),
        ("Which vendor is cheapest for 10 RM-IMPELLER?", "supplier_comparison"),
        ("Fastest supplier for 27 units of RM-IMPELLER, we're late", "supplier_comparison"),
        ("What goes into a FG-PUMP-100?", "bom_explosion"),
        ("Do we have the same part under two codes?", "duplicate_items"),
        ("What stock can we get rid of?", "lifecycle_review"),
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


def test_assistant_commitment_answer_is_grounded_and_cost_gated(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["delta.admin"], "Is it worth paying more to protect order SO-1001?")
    assert "SO-1001/10" in out["answer"]
    assert out["grounding"]["passed"], out["grounding"]
    named = agent.chat(principals["delta.admin"], "Should we pay extra for faster delivery on SO-1002?")
    assert named["tool_calls"][0]["args"]["order_id"] == "SO-1002"
    assert "SO-1002/10" in named["answer"]  # the order asked about, never silently another one
    by_customer = agent.chat(principals["delta.admin"], "How do we save the CUST-HARBOR order?")
    assert "SO-1002/10" in by_customer["answer"]
    assert by_customer["grounding"]["passed"]
    unknown = agent.chat(principals["delta.admin"], "Can we still deliver SO-9999 on time with a faster supplier?")
    assert "SO-9999 is not open in your scope" in unknown["answer"]
    refused = agent.chat(principals["delta.planner"], "Is it worth paying more to protect order SO-1001?")
    assert refused["kind"] == "unsupported"
    assert "555000" not in json.dumps(refused, default=str)


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
        sections = set(c.get("/api/auth/me").json()["sections"])
        assert {"planning", "master_data"} <= sections
        assert "procurement" not in sections  # no cost access: supplier pages are not offered
        assert c.post(
            "/api/planning/assess", json={"question": "Can our capacity handle Ramadan demand?"}
        ).status_code in (401, 403)
        r = c.post("/api/planning/assess", json={"question": "Can our capacity handle Ramadan demand?"}, headers=CSRF)
        assert r.status_code == 200
        assert r.json()["mode"] == "unsupported"


@pytest.mark.security
def test_planning_endpoints_are_rate_limited_per_user(data_dir: Any, tmp_path_factory: pytest.TempPathFactory) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="planning-limit-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("planninglimit") / "app.db"),
        log_level="WARNING",
        rate_limit_planning_per_min=2,
    )
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/planning/duplicates").status_code == 401  # unauthenticated first, never a limit leak
        c.post("/api/auth/dev-login", json={"username": "delta.admin"}, headers=CSRF)
        codes = [c.get("/api/planning/duplicates").status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        assert c.get("/api/inventory/filters").status_code == 200  # other routes keep their own budget


def test_commitment_protection_on_the_pump_order(svc: PlanningService, principals: dict[str, Principal]) -> None:
    listing = svc.commitments(principals["delta.admin"], AS_OF)
    keys = {ln["key"] for ln in listing["at_risk"]}
    assert "SO-1001/10" in keys
    assert "SO-1003/10" not in keys  # on time: nothing to protect
    out = svc.commitment(principals["delta.admin"], "SO-1001/10", AS_OF)
    assert out["at_risk"] is True
    assert out["feasible"] is True
    assert out["recommended_delivery"] == "2026-10-29"
    rec = [o for o in out["options"] if o["recommended"]]
    assert len(rec) == 1
    assert rec[0]["suppliers"] == ["SUP-BETA"]
    by_supplier = {o["suppliers"][0]: o for o in out["options"] if o["kind"] == "supplier"}
    assert by_supplier["SUP-ALPHA"]["eligible"] is False  # 12% rejection exceeds the 5% commitment gate
    assert by_supplier["SUP-ZETA"]["eligible"] is False  # not approved
    assert out["exposure"]["order_value"] == "555000"
    assert out["approval_required"] is True
    assert out["recommendation_only"] is True


def test_commitment_needs_cost_access_and_a_known_order(svc: PlanningService, principals: dict[str, Principal]) -> None:
    with pytest.raises(AppError) as exc:
        svc.commitment(principals["delta.planner"], "SO-1001/10", AS_OF)
    assert exc.value.status_code == 403
    with pytest.raises(AppError) as exc:
        svc.commitment(principals["delta.admin"], "SO-9999/10", AS_OF)
    assert exc.value.status_code == 404


def test_commitment_api(data_dir: Any, tmp_path_factory: pytest.TempPathFactory) -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="commitment-secret-" + "x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("commitdb") / "app.db"),
        log_level="WARNING",
    )
    with TestClient(create_app(settings)) as c:
        assert c.get("/api/planning/commitments").status_code == 401
        c.post("/api/auth/dev-login", json={"username": "delta.planner"}, headers=CSRF)
        assert c.get("/api/planning/commitments").status_code == 403
        assert c.get("/api/planning/commitment?order=SO-1001/10").status_code == 403
    with TestClient(create_app(settings)) as c:
        c.post("/api/auth/dev-login", json={"username": "delta.admin"}, headers=CSRF)
        assert c.get("/api/planning/commitment?order=bad order").status_code == 422
        r = c.get(f"/api/planning/commitment?order=SO-1001/10&as_of={AS_OF.isoformat()}")
        assert r.status_code == 200
        assert r.json()["feasible"] is True


def test_capability_gap_audit_row_fits_the_audit_columns(
    svc: PlanningService, principals: dict[str, Principal], query_service: QueryService
) -> None:
    # SQLite ignores VARCHAR lengths and PostgreSQL enforces them: a long reason code passed here and failed CI there.
    out = svc.assess(principals["delta.admin"], "Can our machine capacity handle Ramadan demand?")
    assert out["capability_gaps"]
    rows = query_service.audit.recent("demo-delta", limit=200)
    gap = next(r for r in rows if r.action == "planning:capability_gap")
    assert gap.reason_code == "capability_gap"
    assert all(len(r.reason_code or "") <= 64 for r in rows)
    assert all(len(r.dataset or "") <= 64 for r in rows)
