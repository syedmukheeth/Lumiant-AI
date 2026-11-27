"""S11 Analyst: business-goal answers (inventory levers), app-computed figures (ADR-0013), the new analysis tools,
the daily AI allowance and request deadline (DEC-037), evidence without run metadata (LA-10) and history answers."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from itertools import count
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

import lumiant.agent.service as service_module
from lumiant.agent.budget import EXHAUSTED_NOTICE
from lumiant.agent.context import MAX_ANSWER_CHARS, HistoryTurn
from lumiant.agent.grounding import evidence_from
from lumiant.agent.providers import GeminiProvider, model_view
from lumiant.agent.service import AgentService
from lumiant.agent.tools import TOOLS, ToolContext, ToolOutput
from lumiant.auth.principal import Principal
from lumiant.core.config import Settings
from lumiant.query.service import QueryService
from lumiant.tenancy.registry import TenantRegistry
from tests.integration.test_agent_v2 import FakeGemini, fn, gtext

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def agent(query_service: QueryService) -> AgentService:
    return AgentService(query_service, Settings(_env_file=None))  # type: ignore[call-arg]


def run(ctx: ToolContext, name: str, args: dict[str, Any] | None = None) -> ToolOutput:
    tool = TOOLS[name]
    out = tool.run(ctx, tool.args.model_validate(args or {}))
    out.index = len(ctx.prior)
    ctx.prior.append(out)
    return out


def with_gemini(query: QueryService, fake: FakeGemini, **settings: Any) -> AgentService:
    patched = AgentService(query, Settings(_env_file=None, **settings))  # type: ignore[call-arg]
    patched._provider = lambda principal: (GeminiProvider("k", "m", client=fake), None)  # type: ignore[method-assign]
    return patched


def table(out: dict[str, Any] | ToolOutput, title: str, kind: str = "table") -> dict[str, Any]:
    blocks = out["blocks"] if isinstance(out, dict) else out.blocks
    return next(b for b in blocks if b["type"] == kind and b["title"].startswith(title))


def money(text: str) -> tuple[str, Decimal]:
    cur, amount = text.split(" ")
    return cur, Decimal(amount.replace(",", ""))


# ------------------------------------------------------------------------------------------- inventory levers
def test_a_profit_question_gets_the_levers_not_a_refusal(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "What should I do to make 200000 profit next month?")
    assert out["kind"] == "tools"
    assert [c["name"] for c in out["tool_calls"]] == ["inventory_levers"]
    assert out["grounding"]["passed"]
    assert "profit cannot be calculated" in out["answer"]
    levers = table(out, "Inventory levers")
    assert {c["key"] for c in levers["columns"]} == {"lever", "finding", "value", "action"}
    by_lever = {r["lever"]: r for r in levers["rows"]}
    assert {"Stock above maximum", "No issue in 270 days", "Expired lots", "Below reorder level"} <= set(by_lever)
    cur, amount = money(by_lever["Stock above maximum"]["value"])
    assert cur == "USD"
    assert amount > 0
    assert all(r["action"] for r in levers["rows"])


def test_excess_value_is_attributed_from_each_pair_exactly(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    """Excess value = Σ pair value × excess ÷ on hand, recomputed here from the same scoped rows in Decimal."""
    admin = principals["alpha.admin"]
    ctx = ToolContext(query_service, admin)
    levers = run(ctx, "inventory_levers")
    excess = run(ctx, "excess_stock")  # same analysis, first 15 rows: every listed pair must be valued the same way
    from lumiant.agent.levers_tools import _pair_values, _share

    pairs, _complete = _pair_values(ctx, {str(r["item_id"]) for r in table(excess, "Excess stock")["rows"]})
    for r in table(excess, "Excess stock")["rows"]:
        got = _share(pairs.get((str(r["item_id"]), str(r["warehouse_id"]))), r["excess"], r["uom"])
        if got is None:
            continue
        pair = pairs[(str(r["item_id"]), str(r["warehouse_id"]))]
        assert got[1] == pair.value * Decimal(r["excess"]) / pair.qty
        assert got[1] <= pair.value  # the excess is part of the pair, never more
    assert table(levers, "Inventory levers")["rows"][0]["lever"] == "Stock above maximum"


@pytest.mark.security
def test_levers_show_no_values_to_a_role_without_cost_access(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["alpha.analyst"], "How can we free up cash tied in stock?")
    assert [c["name"] for c in out["tool_calls"]] == ["inventory_levers"]
    levers = table(out, "Inventory levers")
    assert "value" not in {c["key"] for c in levers["columns"]}
    assert "cannot view values" in out["answer"]
    assert "USD" not in json.dumps(levers)


def test_levers_say_what_an_extract_tenant_cannot_show(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["gamma.admin"], "How do we reduce our inventory carrying costs?")
    rows = table(out, "Inventory levers")["rows"]
    assert any(r["finding"].startswith("Not available") for r in rows)
    assert "valuation price" in out["answer"]
    assert out["grounding"]["passed"]


def test_levers_point_to_order_margins_where_they_are_mapped(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["delta.admin"], "How can we improve margins?")
    assert "Only open customer orders carry selling prices and margins" in out["answer"]


# ------------------------------------------------------------------------------------------- calculate
def test_calculate_shares_a_figure_against_a_number_the_user_typed(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    ctx = ToolContext(query_service, principals["alpha.admin"], question="make 200000 profit next month")
    levers = run(ctx, "inventory_levers")
    out = run(ctx, "calculate", {"op": "share", "operands": [{"ref": "c0.r0.value"}, {"value": "200000"}]})
    assert out.ok, out.answer
    _cur, excess = money(table(levers, "Inventory levers")["rows"][0]["value"])
    expected = (excess / Decimal(200000) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    assert out.data["result"] == str(expected)
    assert "assumes 200000 is in USD" in out.answer


def test_calculate_differences_exactly_in_one_currency(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    ctx = ToolContext(query_service, principals["alpha.admin"])
    by_wh = run(ctx, "stock_by", {"dimension": "warehouse", "measure": "value"})
    rows = table(by_wh, "", "bar")["rows"]
    out = run(ctx, "calculate", {"op": "difference", "operands": [{"ref": "c0.r0.total"}, {"ref": "c0.r1.total"}]})
    assert out.ok, out.answer
    expected = (Decimal(str(rows[0]["total"])) - Decimal(str(rows[1]["total"]))).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert out.data["result"] == str(expected)
    assert out.data["unit"] == "USD"


@pytest.mark.security
def test_calculate_never_combines_currencies(query_service: QueryService, principals: dict[str, Principal]) -> None:
    ctx = ToolContext(query_service, principals["beta.admin"])
    by_wh = run(ctx, "stock_by", {"dimension": "warehouse", "measure": "value"})
    rows = table(by_wh, "", "bar")["rows"]
    first = rows[0]["currency"]
    other = next(i for i, r in enumerate(rows) if r["currency"] != first)
    out = run(ctx, "calculate", {"op": "sum", "operands": [{"ref": "c0.r0.total"}, {"ref": f"c0.r{other}.total"}]})
    assert not out.ok
    assert "Cannot combine" in out.answer
    assert "different currencies" in out.answer


@pytest.mark.security
def test_calculate_refuses_numbers_that_are_not_evidence(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    ctx = ToolContext(query_service, principals["alpha.admin"], question="compare with last year")
    run(ctx, "inventory_summary")
    out = run(ctx, "calculate", {"op": "ratio", "operands": [{"ref": "c0.r0.value"}, {"value": "123456"}]})
    assert not out.ok
    assert "does not appear" in out.answer
    bad_ref = run(ctx, "calculate", {"op": "sum", "operands": [{"ref": "c9.r0.value"}, {"ref": "c0.r0.value"}]})
    assert not bad_ref.ok
    assert "no successful result c9" in bad_ref.answer


def test_calculate_refuses_division_by_zero(query_service: QueryService, principals: dict[str, Principal]) -> None:
    ctx = ToolContext(query_service, principals["alpha.admin"], question="divide by 0")
    run(ctx, "inventory_summary")
    out = run(ctx, "calculate", {"op": "ratio", "operands": [{"ref": "c0.r0.value"}, {"value": "0"}]})
    assert not out.ok
    assert "divide by zero" in out.answer


def test_calculate_arguments_are_checked() -> None:
    args = TOOLS["calculate"].args
    with pytest.raises(ValidationError):
        args.model_validate({"op": "sum", "operands": [{"ref": "c0.r0.value", "value": "1"}, {"value": "2"}]})
    with pytest.raises(ValidationError):
        args.model_validate({"op": "sum", "operands": [{"value": "1e9"}, {"value": "2"}]})


# ------------------------------------------------------------------------------------------- analysis tools
def test_ageing_questions_route_to_stock_ageing(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "How old is our stock?")
    assert [c["name"] for c in out["tool_calls"]] == ["stock_ageing"]
    rows = table(out, "Stock ageing")["rows"]
    assert [r["bucket"] for r in rows][-1] == "Never issued"
    assert len(rows) == 5
    assert out["grounding"]["passed"]


def test_trend_questions_rebuild_the_value_trend_with_a_chart(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["alpha.admin"], "Show the inventory value trend over the last 6 months")
    assert out["tool_calls"] == [{"name": "value_trend", "args": {"months": 6}}]
    chart = next(b for b in out["blocks"] if b["type"] == "chart")
    assert chart["variant"] == "line"
    assert chart["x_key"] == "period"
    assert chart["rows"] == table(out, "Inventory value")["rows"]
    assert all(isinstance(r["value"], (str, type(None))) for r in chart["rows"])  # money stays a string
    assert out["grounding"]["passed"]


@pytest.mark.security
def test_trends_need_cost_access(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.analyst"], "How has inventory value changed month by month?")
    assert out["kind"] == "unsupported"
    assert out["blocks"] == []


def test_computed_abc_uses_the_cutoffs_given(query_service: QueryService, principals: dict[str, Principal]) -> None:
    ctx = ToolContext(query_service, principals["alpha.admin"])
    out = run(ctx, "computed_abc", {"a_pct": 80, "b_pct": 95})
    assert out.ok
    assert out.provenance is not None
    assert "A up to 80%" in out.answer
    with pytest.raises(ValidationError):
        TOOLS["computed_abc"].args.model_validate({"a_pct": 90, "b_pct": 80})
    with pytest.raises(ValidationError):
        TOOLS["computed_abc"].args.model_validate({})  # no default cutoffs: the model must ask


@pytest.mark.security
def test_open_purchase_orders_keep_the_users_scope(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    admin = run(ToolContext(query_service, principals["alpha.admin"]), "open_purchase_orders")
    assert admin.data["overdue_lines"] <= admin.data["open_lines"]
    analyst = run(ToolContext(query_service, principals["alpha.analyst"]), "open_purchase_orders")
    rows = table(analyst, "Open purchase orders")["rows"]
    assert {r["warehouse_id"] for r in rows} <= {"3100"}
    assert "unit_price" not in {c["key"] for c in table(analyst, "Open purchase orders")["columns"]}


# ------------------------------------------------------------------------------------------- Gemini (fake client)
def test_gemini_may_word_an_app_computed_figure(query_service: QueryService, principals: dict[str, Principal]) -> None:
    admin = principals["alpha.admin"]
    question = "What should I do to make 200000 profit next month?"
    ctx = ToolContext(query_service, admin, question=question)
    run(ctx, "inventory_levers")
    expected = run(ctx, "calculate", {"op": "share", "operands": [{"ref": "c0.r0.value"}, {"value": "200000"}]})
    share = expected.data["result"]
    prose = f"Freeing stock above maximum would cover {share}% of the 200000 target.\n- Stop buying excess items."
    fake = FakeGemini(
        fn(("inventory_levers", {})),
        fn(("calculate", {"op": "share", "operands": [{"ref": "c0.r0.value"}, {"value": "200000"}]})),
        gtext(prose),
    )
    out = with_gemini(query_service, fake).chat(admin, question)
    assert [c["name"] for c in out["tool_calls"]] == ["inventory_levers", "calculate"]
    assert out["grounding"]["source"] == "model", out["grounding"]
    assert out["answer"] == prose
    config = fake.calls[0]["config"]
    assert config["max_output_tokens"] == 1024
    assert config["temperature"] == 0.2
    sent = json.dumps(fake.calls[1]["contents"][-1], default=str)
    assert '"ref": "c0.r0"' in sent  # the model sees the references calculate accepts


def test_gemini_cannot_launder_its_own_arithmetic(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    fake = FakeGemini(fn(("inventory_levers", {})), gtext("Together the levers free 999999.99 of cash."))
    out = with_gemini(query_service, fake).chat(principals["alpha.admin"], "How do we free up cash?")
    assert out["grounding"]["source"] == "template"
    assert "999999.99" in out["grounding"]["ungrounded"]


def test_spent_allowance_falls_back_to_built_in_matching(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    fake = FakeGemini(fn(("excess_stock", {})))
    agent = with_gemini(query_service, fake, ai_daily_calls=1)
    first = agent.chat(principals["delta.admin"], "Which items are in excess?")
    assert first["notice"] == EXHAUSTED_NOTICE  # the review round had no allowance left
    assert first["grounding"]["source"] == "template"
    assert any(s.get("detail") == "AI allowance used up" for s in first["steps"])
    second = agent.chat(principals["delta.admin"], "Which items are in excess?")
    assert second["mode"] == "rules"
    assert second["notice"] == EXHAUSTED_NOTICE
    assert len(fake.calls) == 1  # the model was asked once, then never again


def test_the_request_deadline_stops_further_model_rounds(
    query_service: QueryService, principals: dict[str, Principal], monkeypatch: pytest.MonkeyPatch
) -> None:
    ticks = count(step=100)  # every clock read is 100 s later than the last
    monkeypatch.setattr(service_module, "time", SimpleNamespace(perf_counter=lambda: float(next(ticks))))
    fake = FakeGemini(fn(("excess_stock", {})))
    out = with_gemini(query_service, fake).chat(principals["alpha.admin"], "Which items are in excess?")
    assert any(s.get("detail") == "time limit reached" for s in out["steps"])
    assert "took too long" in (out["notice"] or "")
    assert len(fake.calls) == 1


@pytest.mark.security
def test_an_earlier_answer_is_context_never_evidence(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    history = [
        HistoryTurn(question="What is our inventory worth?", tool="inventory_summary", answer="It is 987654.32.")
    ]
    fake = FakeGemini(fn(("excess_stock", {})), gtext("Earlier it was 987654.32."))
    out = with_gemini(query_service, fake).chat(principals["alpha.admin"], "And the excess?", history=history)
    assert out["grounding"]["source"] == "template"
    assert "987654.32" in out["grounding"]["ungrounded"]
    assert "Earlier answer, for context only" in json.dumps(fake.calls[0]["contents"], default=str)


def test_history_keeps_reusable_args_and_drops_the_rest() -> None:
    """A follow-up after query_inventory, calculate or a long definition search must not be rejected (422)."""
    turn = HistoryTurn.model_validate(
        {
            "question": "q",
            "tool": "query_inventory",
            "args": {
                "dataset": "stock_balance",
                "measures": [{"field": "quantity", "agg": "sum"}],
                "query": "x" * 150,
                "limit": 25,
                "group_by": ["warehouse_id"],
            },
        }
    )
    assert turn.args == {"dataset": "stock_balance", "limit": 25, "group_by": ["warehouse_id"]}


def test_history_answers_are_cleaned_and_capped() -> None:
    turn = HistoryTurn(question="q", answer="line\x00one\n" + "x" * 400)
    assert turn.answer is not None
    assert "\x00" not in turn.answer
    assert "\n" not in turn.answer
    assert len(turn.answer) == MAX_ANSWER_CHARS


def test_model_view_rows_carry_their_references() -> None:
    out = ToolOutput("t", "t", "s", [{"type": "table", "columns": [], "rows": [{"n": "5"}, {"n": "6"}]}], index=3)
    view = model_view(out)
    assert [r["ref"] for r in view["rows"]] == ["c3.r0", "c3.r1"]


@pytest.mark.security
def test_run_metadata_is_not_evidence() -> None:
    out = ToolOutput(
        "t",
        "t",
        "s",
        [{"type": "table", "rows": [{"n": "5"}]}],
        data={"rows": [{"n": "5"}], "provenance": {"duration_ms": 12.5, "data_as_of": "2026-11-25"}, "ms": 777},
    )
    evidence = evidence_from("question with 42", [out])
    assert {"5", "42", "2026"} <= evidence
    assert "12.5" not in evidence
    assert "777" not in evidence


# ------------------------------------------------------------------------------------------- tenants
def test_every_synthetic_demo_tenant_is_approved_for_external_ai(registry: TenantRegistry) -> None:
    demos = [t for t in registry if t.id.startswith("demo-")]
    assert len(demos) == 4
    assert all(t.synthetic and t.ai.external_provider_approved for t in demos)
