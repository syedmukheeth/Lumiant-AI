"""Part C (ADR-0009, ADR-0010): Gemini provider, screen context, follow-ups, concentration, insights and streaming."""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from lumiant.agent.context import ChatContext, ContextFilters, HistoryTurn, Selection
from lumiant.agent.providers import GeminiProvider, build_provider, gemini_declaration
from lumiant.agent.service import AgentService
from lumiant.agent.tools import TOOLS, tools_for
from lumiant.analyses.below_reorder import BelowReorderFilters, run_below_reorder
from lumiant.analyses.concentration import run_concentration
from lumiant.auth.principal import Principal
from lumiant.core.config import Settings
from lumiant.insights.engine import InsightService
from lumiant.main import create_app
from lumiant.query.plan import QueryPlan
from lumiant.query.service import QueryService
from tests.helpers import app_db_url

pytestmark = pytest.mark.integration
CSRF = {"X-Requested-With": "lumiant"}


@pytest.fixture(scope="module")
def agent(query_service: QueryService) -> AgentService:
    return AgentService(query_service, Settings(_env_file=None))  # type: ignore[call-arg]


def ctx(*selections: tuple[str, str], page: str = "overview", **filters: str) -> ChatContext:
    return ChatContext(
        page=page,
        filters=ContextFilters(**filters),
        selections=[Selection(kind=k, id=i, label="label 999999") for k, i in selections],  # type: ignore[arg-type]
    )


def calls(out: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [(c["name"], c["args"]) for c in out["tool_calls"]]


# ------------------------------------------------------------------------------------------- screen context
def test_selected_warehouse_is_explained_by_its_item_groups_and_top_items(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["alpha.admin"], "why is this so high?", ctx(("warehouse", "1100")))
    assert calls(out) == [
        ("stock_by", {"dimension": "item_group", "measure": "value", "warehouse_id": "1100"}),
        ("top_value_items", {"limit": 5, "warehouse_id": "1100"}),
    ]
    assert out["grounding"]["passed"]
    assert "1100" in out["answer"]


def test_selection_labels_are_never_used_or_trusted(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "explain this", ctx(("warehouse", "1100")))
    blob = json.dumps(out["tool_calls"])
    assert "label" not in blob
    assert "999999" not in blob
    assert "999999" not in out["answer"]


def test_two_selections_of_one_kind_are_compared(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "compare these", ctx(("warehouse", "1100"), ("warehouse", "2100")))
    assert calls(out) == [("stock_by", {"dimension": "warehouse", "measure": "value", "only": ["1100", "2100"]})]
    labels = {r["warehouse.name"] for r in out["blocks"][0]["rows"]}
    assert len(labels) == 2


@pytest.mark.security
def test_out_of_scope_selection_is_refused_before_any_tool_runs(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["alpha.north_manager"], "explain this", ctx(("warehouse", "2100")))
    assert out["kind"] == "unsupported"
    assert out["tool_calls"] == []
    assert "outside the warehouses you can see" in out["answer"]
    filtered = agent.chat(principals["alpha.north_manager"], "Show the highest-value items", ctx(warehouse_id="3100"))
    assert filtered["tool_calls"] == []


@pytest.mark.security
def test_unknown_selected_item_is_refused(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "explain this", ctx(("item", "NOPE-NOT-AN-ITEM")))
    assert out["kind"] == "unsupported"
    assert out["tool_calls"] == []


def test_page_filters_narrow_explicit_questions(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(
        principals["alpha.admin"], "Show the highest-value items", ctx(page="inventory", warehouse_id="1100")
    )
    assert calls(out) == [("top_value_items", {"limit": 10, "warehouse_id": "1100"})]
    # Grouping by the filtered field keeps the comparison: the filter is not applied to it.
    by = agent.chat(principals["alpha.admin"], "Show inventory value by warehouse", ctx(warehouse_id="1100"))
    assert calls(by) == [("stock_by", {"dimension": "warehouse", "measure": "value"})]


def test_narrowed_totals_match_an_independent_filtered_query(
    agent: AgentService, principals: dict[str, Principal], query_service: QueryService
) -> None:
    out = agent.chat(principals["alpha.admin"], "why is this high?", ctx(("warehouse", "1100")))
    groups = out["blocks"][0]["rows"]
    total = sum(Decimal(r["total"]) for r in groups)
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "measures": [{"field": "stock_value", "agg": "sum", "alias": "v"}],
            "filters": [{"field": "warehouse_id", "op": "eq", "value": "1100"}],
        }
    )
    expected = query_service.run_plan(plan, principals["alpha.admin"], action="test").rows[0]["v"]
    assert total == Decimal(expected)


def test_role_without_cost_access_gets_quantities_for_a_selection(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["alpha.analyst"], "explain this", ctx(("item_group", "PUMP")))
    assert calls(out) == [("stock_by", {"dimension": "warehouse", "measure": "quantity", "item_group": "PUMP"})]
    assert "USD" not in json.dumps(out)


def test_metric_selection_breaks_the_kpi_down(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "analyze", ctx(("metric", "inventory_value_total")))
    assert [c[0] for c in calls(out)] == ["stock_by", "concentration"]


# ------------------------------------------------------------------------------------------- follow-ups
def test_follow_up_reuses_the_previous_tool_with_the_change(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    history = [
        HistoryTurn(
            question="Show inventory value by warehouse",
            tool="stock_by",
            args={"dimension": "warehouse", "measure": "value"},
        )
    ]
    out = agent.chat(principals["alpha.admin"], "what about quantity?", None, history)
    assert calls(out) == [("stock_by", {"dimension": "warehouse", "measure": "quantity"})]
    regroup = agent.chat(principals["alpha.admin"], "and by item group?", None, history)
    assert calls(regroup) == [("stock_by", {"dimension": "item_group", "measure": "value"})]


@pytest.mark.security
def test_follow_up_cannot_switch_a_viewer_to_values(agent: AgentService, principals: dict[str, Principal]) -> None:
    history = [
        HistoryTurn(
            question="Which warehouse has the most stock?",
            tool="stock_by",
            args={"dimension": "warehouse", "measure": "quantity"},
        )
    ]
    out = agent.chat(principals["alpha.analyst"], "what about value?", None, history)
    assert out["tool_calls"] == []
    assert "USD" not in json.dumps(out)


# ------------------------------------------------------------------------------------------- concentration + insights
def test_concentration_is_consistent_with_the_value_total(
    principals: dict[str, Principal], query_service: QueryService
) -> None:
    res = run_concentration(query_service, principals["alpha.admin"])
    usd = next(c for c in res["currencies"] if c["currency"] == "USD")
    plan = QueryPlan.model_validate(
        {
            "dataset": "stock_balance",
            "measures": [{"field": "stock_value", "agg": "sum", "alias": "v"}],
            "filters": [{"field": "quantity", "op": "gt", "value": "0"}],
        }
    )
    assert usd["total"] == Decimal(query_service.run_plan(plan, principals["alpha.admin"], action="test").rows[0]["v"])
    assert usd["complete"]
    assert 0 < usd["items_for_target"] <= usd["stocked_items"]
    cumulative = [r["cumulative_pct"] for r in res["top"] if r["currency"] == "USD"]
    assert cumulative == sorted(cumulative)


def test_concentration_tool_answer_is_grounded(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "Which items make up most of the value? (pareto)")
    assert calls(out)[0][0] == "concentration"
    assert out["grounding"]["passed"]
    assert out["grounding"]["source"] == "template"
    assert out["provenance"]


def test_insight_counts_match_the_analyses(principals: dict[str, Principal], query_service: QueryService) -> None:
    feed = InsightService(query_service).feed(principals["alpha.admin"], fresh=True)
    below = next(i for i in feed["insights"] if i["id"] == "below_reorder")
    flagged = run_below_reorder(query_service, principals["alpha.admin"], BelowReorderFilters(), limit=1, offset=0)
    assert below["metrics"][0]["value"] == int((flagged.summary or {})["flagged"])
    severities = [i["severity"] for i in feed["insights"]]
    assert severities == sorted(severities, key=["critical", "warning", "info"].index)


@pytest.mark.security
def test_insights_respect_cost_access_and_report_gaps(
    principals: dict[str, Principal], query_service: QueryService
) -> None:
    service = InsightService(query_service)
    viewer = service.feed(principals["alpha.analyst"], fresh=True)
    assert "USD" not in json.dumps(viewer)
    gamma = service.feed(principals["gamma.admin"], fresh=True)
    gaps = {g["id"]: g for g in gamma["gaps"]}
    assert {"dormant", "below_reorder", "expiring_lots"} <= set(gaps)
    assert "MB51" in gaps["dormant"]["needs"]
    assert any(i["category"] == "availability" for i in gamma["insights"])  # stock tied up in QI / blocked


def test_insights_tool_routes_from_open_questions(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "What should I look at today?")
    assert calls(out) == [("insights", {})]
    assert out["grounding"]["passed"]


# ------------------------------------------------------------------------------------------- Gemini provider
class FakeGemini:
    def __init__(self, *responses: Any) -> None:
        self.calls: list[dict[str, Any]] = []
        self._responses = list(responses)
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._responses.pop(0)


def fn_call(name: str, **args: Any) -> Any:
    return SimpleNamespace(
        function_calls=[SimpleNamespace(name=name, args=args)],
        candidates=[SimpleNamespace(content={"role": "model", "parts": [{"function_call": {"name": name}}]})],
        text=None,
    )


def gtext(value: str) -> Any:
    return SimpleNamespace(function_calls=None, candidates=[SimpleNamespace(content={"role": "model"})], text=value)


def with_provider(agent: AgentService, provider: Any) -> AgentService:
    patched = AgentService(agent.query, agent.settings)
    patched._provider = lambda principal: (provider, None)  # type: ignore[method-assign]
    return patched


def test_gemini_declarations_are_clean_json_schema() -> None:
    decl = {d["name"]: d for d in (gemini_declaration(t) for t in TOOLS.values())}
    assert "parameters_json_schema" not in decl["below_reorder"]  # no-argument tools declare no parameters
    schema = decl["stock_by"]["parameters_json_schema"]
    assert "title" not in json.dumps(schema)
    assert "additionalProperties" not in json.dumps(schema)
    assert set(schema["properties"]) >= {"dimension", "measure", "only", "warehouse_id"}


def test_gemini_chooses_tools_and_its_grounded_wording_is_used(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    client = FakeGemini(fn_call("below_reorder"), gtext("Several items are below their reorder level."))
    out = with_provider(agent, GeminiProvider("k", "gemini-flash-latest", client=client)).chat(
        principals["alpha.analyst"], "what is running low?", ctx(("warehouse", "3100")), []
    )
    first, second = client.calls
    declared = {d["name"] for d in first["config"]["tools"][0]["function_declarations"]}
    assert declared == {t.name for t in tools_for(principals["alpha.analyst"])}
    assert first["config"]["automatic_function_calling"] == {"disable": True}
    system = first["config"]["system_instruction"]
    assert "never write SQL" in system
    assert "warehouse 3100" in system
    assert "999999" not in system
    reply = second["contents"][-1]
    assert reply["role"] == "tool"
    assert len(reply["parts"][0]["function_response"]["response"]["rows"]) <= 20
    assert out["mode"] == "gemini"
    assert out["grounding"]["source"] == "model"
    assert out["answer"] == "Several items are below their reorder level."


@pytest.mark.security
def test_gemini_invented_numbers_are_rejected(agent: AgentService, principals: dict[str, Principal]) -> None:
    client = FakeGemini(fn_call("below_reorder"), gtext("Exactly 987654 items are below reorder."))
    out = with_provider(agent, GeminiProvider("k", "m", client=client)).chat(principals["alpha.admin"], "what is low?")
    assert out["grounding"]["source"] == "template"
    assert "987654" not in out["answer"]


def test_gemini_failure_falls_back_to_rules(agent: AgentService, principals: dict[str, Principal]) -> None:
    class Broken:
        models = SimpleNamespace(generate_content=lambda **_: (_ for _ in ()).throw(TimeoutError()))

    out = with_provider(agent, GeminiProvider("k", "m", client=Broken())).chat(
        principals["alpha.admin"], "Which items are below reorder level?"
    )
    assert out["mode"] == "rules"
    assert "unavailable" in (out["notice"] or "")
    assert calls(out) == [("below_reorder", {})]


def test_gemini_needs_tenant_approval_and_a_key() -> None:
    provider, notice = build_provider(configured="gemini", api_key="k", model="m", tenant_approved=False)
    assert provider.name == "rules"
    assert "not approved" in (notice or "")
    provider, notice = build_provider(configured="gemini", api_key=None, model="m", tenant_approved=True)
    assert provider.name == "rules"
    assert "not configured" in (notice or "")


# ------------------------------------------------------------------------------------------- HTTP: stream + insights
@pytest.fixture(scope="module")
def client(data_dir: Path, tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        auth_mode="dev",
        dev_jwt_secret="x" * 40,
        data_dir=data_dir,
        app_db_url=app_db_url(tmp_path_factory.mktemp("ctx-appdb") / "app.db"),
        log_level="WARNING",
        rate_limit_enabled=False,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def login(client: TestClient, username: str) -> None:
    client.cookies.clear()
    assert client.post("/api/auth/dev-login", json={"username": username}, headers=CSRF).status_code == 200


def parse_sse(text: str) -> list[dict[str, Any]]:
    return [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: ")]


def test_stream_sends_steps_then_the_same_answer_as_chat(client: TestClient) -> None:
    login(client, "alpha.admin")
    body = {
        "message": "explain this",
        "context": {"page": "overview", "selections": [{"kind": "warehouse", "id": "1100"}]},
    }
    r = client.post("/api/agent/chat/stream", json=body, headers=CSRF)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "step"
    assert kinds[-1] == "answer"
    assert "block" in kinds
    running = [e["id"] for e in events if e["type"] == "step" and e["status"] == "running"]
    assert running[:2] == ["understand", "tool:0"]
    answer = events[-1]["answer"]
    plain = client.post("/api/agent/chat", json=body, headers=CSRF).json()
    assert answer["tool_calls"] == plain["tool_calls"]
    assert answer["answer"] == plain["answer"]
    assert [s["id"] for s in answer["steps"]][-1] == "ground"


@pytest.mark.security
def test_stream_needs_csrf_and_validates_context(client: TestClient) -> None:
    login(client, "alpha.admin")
    assert client.post("/api/agent/chat/stream", json={"message": "hello there"}).status_code == 403
    too_many = [{"kind": "warehouse", "id": str(i)} for i in range(6)]
    for context in (
        {"selections": too_many},
        {"selections": [{"kind": "warehouse", "id": "11\x0000"}]},
        {"selections": [{"kind": "table", "id": "ZV_STOCK"}]},
        {"sql": "select 1"},
    ):
        r = client.post("/api/agent/chat", json={"message": "explain this", "context": context}, headers=CSRF)
        assert r.status_code == 422, context


def test_insights_endpoint(client: TestClient) -> None:
    login(client, "alpha.admin")
    r = client.get("/api/insights")
    assert r.status_code == 200
    body = r.json()
    assert body["insights"]
    assert {"id", "severity", "title", "ask", "metrics"} <= set(body["insights"][0])
    login(client, "gamma.viewer")
    viewer = client.get("/api/insights").json()
    assert "SAR" not in json.dumps(viewer)
