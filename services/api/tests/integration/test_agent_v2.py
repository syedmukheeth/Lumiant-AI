"""Product v2 P2: multi-step Gemini loop, `query_inventory` (typed plans, ADR-0002) and knowledge retrieval."""

from __future__ import annotations

import re
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from lumiant.agent.data_tools import QueryArgs, catalog_note, to_plan
from lumiant.agent.knowledge_tools import KnowledgeArgs
from lumiant.agent.providers import MAX_ROUNDS, GeminiProvider, model_view
from lumiant.agent.service import AgentService
from lumiant.agent.tools import TOOLS, ToolContext, ToolOutput, tools_for
from lumiant.auth.principal import Principal
from lumiant.canonical.catalog import CATALOG
from lumiant.core.config import Settings
from lumiant.knowledge import KnowledgeIndex, product_index
from lumiant.knowledge.index import Chunk
from lumiant.query.plan import QueryPlan
from lumiant.query.service import QueryService

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def agent(query_service: QueryService) -> AgentService:
    return AgentService(query_service, Settings(_env_file=None))  # type: ignore[call-arg]


class FakeGemini:
    def __init__(self, *responses: Any, vectors: dict[str, list[float]] | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.embeds: list[dict[str, Any]] = []
        self._responses = list(responses)
        self._vectors = vectors or {}
        self.models = SimpleNamespace(generate_content=self._generate, embed_content=self._embed)

    def _generate(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._responses.pop(0)

    def _embed(self, **kwargs: Any) -> Any:
        self.embeds.append(kwargs)
        vec = [self._vectors.get(t[:20], [0.0, 1.0]) for t in kwargs["contents"]]
        return SimpleNamespace(embeddings=[SimpleNamespace(values=v) for v in vec])


def fn(*calls: tuple[str, dict[str, Any]]) -> Any:
    return SimpleNamespace(
        function_calls=[SimpleNamespace(name=n, args=a) for n, a in calls],
        candidates=[SimpleNamespace(content={"role": "model", "parts": [{"function_call": {"name": calls[0][0]}}]})],
        text=None,
    )


def gtext(value: str) -> Any:
    return SimpleNamespace(function_calls=None, candidates=[SimpleNamespace(content={"role": "model"})], text=value)


def with_provider(agent: AgentService, provider: Any) -> AgentService:
    patched = AgentService(agent.query, agent.settings)
    patched._provider = lambda principal: (provider, None)  # type: ignore[method-assign]
    return patched


QTY_BY_WAREHOUSE = {
    "dataset": "stock_balance",
    "group_by": ["warehouse_id"],
    "measures": [{"field": "quantity", "agg": "sum", "alias": "on_hand"}],
    "order_by": "warehouse_id",
    "descending": False,
}


# ------------------------------------------------------------------------------------------- query_inventory
def test_query_inventory_equals_the_same_plan_run_directly(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    admin = principals["alpha.admin"]
    out = TOOLS["query_inventory"].run(ToolContext(query_service, admin), QueryArgs.model_validate(QTY_BY_WAREHOUSE))
    assert out.ok
    direct = query_service.run_plan(
        QueryPlan.model_validate(
            {
                "dataset": "stock_balance",
                "dimensions": ["warehouse_id"],
                "measures": [{"field": "quantity", "agg": "sum", "alias": "on_hand"}],
                "order_by": [{"field": "warehouse_id", "direction": "asc"}],
                "limit": 25,
            }
        ),
        admin,
        action="test",
    ).payload()["data"]
    table = next(b for b in out.blocks if b["type"] == "table")
    assert table["rows"] == direct
    assert {c["key"] for c in table["columns"]} >= {"warehouse_id", "on_hand", "uom"}  # unit added by the engine
    assert next(c for c in table["columns"] if c["key"] == "on_hand")["kind"] == "qty"
    assert out.provenance is not None


@pytest.mark.security
def test_query_inventory_keeps_the_users_warehouse_scope(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    analyst = principals["alpha.analyst"]  # warehouse 3100 only
    out = TOOLS["query_inventory"].run(ToolContext(query_service, analyst), QueryArgs.model_validate(QTY_BY_WAREHOUSE))
    rows = next(b for b in out.blocks if b["type"] == "table")["rows"]
    assert rows
    assert {r["warehouse_id"] for r in rows} == {"3100"}


@pytest.mark.security
def test_query_inventory_refuses_cost_fields_without_cost_access(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    bad = {
        "dataset": "stock_balance",
        "group_by": ["warehouse_id"],
        "measures": [{"field": "stock_value", "agg": "sum"}],
    }
    client = FakeGemini(fn(("query_inventory", bad)), gtext("Values are 123456."))
    out = with_provider(agent, GeminiProvider("k", "m", client=client)).chat(principals["alpha.analyst"], "value?")
    assert out["tool_calls"][0]["name"] == "query_inventory"
    assert out["steps"][1]["status"] == "failed"
    assert "123456" not in out["answer"]  # failed last round: model wording is never used
    assert out["grounding"]["source"] == "template"


def test_catalog_note_lists_canonical_fields_only_and_hides_cost_fields(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    admin_note = catalog_note(ToolContext(query_service, principals["alpha.admin"]))
    analyst_note = catalog_note(ToolContext(query_service, principals["alpha.analyst"]))
    assert "stock_balance" in admin_note
    assert "stock_value" in admin_note
    assert "stock_value" not in analyst_note
    assert "valuation_price" not in analyst_note
    physical = {t.split(".")[-1].lower() for t in query_service.mapping("demo-alpha").physical_tables()}
    words = set(re.findall(r"[a-z0-9_]+", admin_note.lower()))
    assert physical
    assert not (physical - set(CATALOG)) & words  # physical table names never reach the model


def test_float_filter_values_become_exact_decimal_strings() -> None:
    args = QueryArgs.model_validate(
        {
            "dataset": "stock_balance",
            "group_by": ["item_id"],
            "filters": [{"field": "quantity", "op": "gt", "value": 10.5}],
        }
    )
    plan = to_plan(args)
    assert plan.filters[0].value == "10.5"  # type: ignore[union-attr]
    assert Decimal(str(plan.filters[0].value)) == Decimal("10.5")  # type: ignore[union-attr]


def test_invalid_plan_is_returned_to_the_model_as_a_failed_result(
    query_service: QueryService, principals: dict[str, Principal]
) -> None:
    args = QueryArgs.model_validate({"dataset": "stock_balance"})  # no grouping and no measure
    out = TOOLS["query_inventory"].run(ToolContext(query_service, principals["alpha.admin"]), args)
    assert not out.ok
    assert "not valid" in out.answer


# ------------------------------------------------------------------------------------------- multi-step loop
def test_gemini_chains_tools_across_rounds_and_its_grounded_answer_is_used(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    client = FakeGemini(
        fn(("query_inventory", QTY_BY_WAREHOUSE)),
        fn(("below_reorder", {})),
        gtext("Stock is spread across your warehouses and some items are below their reorder level."),
    )
    out = with_provider(agent, GeminiProvider("k", "m", client=client)).chat(
        principals["alpha.admin"], "where is stock and what is running low?"
    )
    assert [c["name"] for c in out["tool_calls"]] == ["query_inventory", "below_reorder"]
    assert len(client.calls) == 3
    second, third = client.calls[1], client.calls[2]
    assert second["contents"][-1]["role"] == "tool"
    assert third["contents"][-1]["parts"][0]["function_response"]["name"] == "below_reorder"
    assert [s["id"] for s in out["steps"] if s["id"].startswith("think:")] == ["think:1", "think:2"]
    assert out["grounding"]["source"] == "model"
    assert out["answer"].startswith("Stock is spread")


@pytest.mark.security
def test_round_limit_forces_a_final_answer_without_tools(agent: AgentService, principals: dict[str, Principal]) -> None:
    rounds = [fn(("below_reorder", {})) for _ in range(MAX_ROUNDS)]
    client = FakeGemini(*rounds, gtext("Some items are below their reorder level."))
    out = with_provider(agent, GeminiProvider("k", "m", client=client)).chat(principals["alpha.admin"], "low stock?")
    assert len(out["tool_calls"]) == MAX_ROUNDS
    last = client.calls[-1]
    assert last["config"]["tool_config"] == {"function_calling_config": {"mode": "NONE"}}
    assert "do not call more tools" in last["config"]["system_instruction"]
    assert out["grounding"]["source"] == "model"


@pytest.mark.security
def test_invented_numbers_after_several_rounds_are_rejected(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    client = FakeGemini(
        fn(("below_reorder", {})),
        fn(("excess_stock", {})),
        gtext("Exactly 4242424 items need attention."),
    )
    out = with_provider(agent, GeminiProvider("k", "m", client=client)).chat(principals["alpha.admin"], "problems?")
    assert "4242424" not in out["answer"]
    assert out["grounding"]["ungrounded"] == ["4242424"]


def test_failed_advance_falls_back_to_the_template_answer(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    class HalfBroken(FakeGemini):
        def _generate(self, **kwargs: Any) -> Any:
            if self.calls:
                raise TimeoutError
            return super()._generate(**kwargs)

    client = HalfBroken(fn(("below_reorder", {})))
    out = with_provider(agent, GeminiProvider("k", "m", client=client)).chat(principals["alpha.admin"], "low?")
    assert out["grounding"]["source"] == "template"
    assert any(s["id"] == "think:1" and s["status"] == "failed" for s in out["steps"])


# ------------------------------------------------------------------------------------------- knowledge
def test_definition_questions_are_answered_from_the_knowledge_base_offline(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["alpha.analyst"], "How is inventory value calculated?")
    assert [c["name"] for c in out["tool_calls"]] == ["search_knowledge"]
    assert "valuation price" in out["answer"]
    sources = next(b for b in out["blocks"] if b["type"] == "sources")
    assert sources["items"][0]["heading"] == "Inventory value"
    assert out["grounding"]["passed"]


def test_data_questions_still_go_to_the_data(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "Which items are below reorder level?")
    assert [c["name"] for c in out["tool_calls"]] == ["below_reorder"]


def test_keyword_search_finds_the_right_definition() -> None:
    index = product_index()
    assert index.search("dormant slow moving stock")[0].chunk.heading == "Dormant or slow-moving stock"
    assert index.search("what is a plant in SAP")[0].chunk.heading == "SAP terms"
    assert index.best_keyword("weather tomorrow in paris") is None


def test_embeddings_are_fused_with_keywords_and_failures_fall_back() -> None:
    chunks = [Chunk("a", "Doc", "Alpha", "apples and pears"), Chunk("b", "Doc", "Beta", "boats and ships")]
    index = KnowledgeIndex(chunks)

    def embedder(texts: list[str], task: str) -> list[list[float]]:
        return [[1.0, 0.0] if ("boat" in t or "vessel" in t) else [0.0, 1.0] for t in texts]

    # No keyword overlap with "vessel", but the dense signal finds the boats chunk.
    assert index.search("vessel", embedder=embedder, embed_key="t")[0].chunk.id == "b"

    def broken(texts: list[str], task: str) -> list[list[float]]:
        raise TimeoutError

    assert index.search("apples", embedder=broken, embed_key="x")[0].chunk.id == "a"


def test_gemini_embeds_for_knowledge_search_and_the_model_sees_the_passages(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    client = FakeGemini(
        fn(("search_knowledge", {"query": "how is FIFO calculated"})), gtext("FIFO consumes the oldest layers first.")
    )
    out = with_provider(agent, GeminiProvider("k", "m", client=client)).chat(principals["alpha.admin"], "explain fifo")
    assert client.embeds
    assert client.embeds[0]["model"] == "gemini-embedding-001"
    response = client.calls[1]["contents"][-1]["parts"][0]["function_response"]["response"]
    assert response["passages"]
    assert out["answer"] == "FIFO consumes the oldest layers first."


def test_model_view_marks_failed_results(query_service: QueryService, principals: dict[str, Principal]) -> None:
    failed = model_view(ToolOutput("x", "x", "nope", ok=False))
    assert failed["status"] == "failed"
    found = TOOLS["search_knowledge"].run(
        ToolContext(query_service, principals["alpha.admin"]), KnowledgeArgs(query="moving weighted average")
    )
    assert model_view(found)["passages"][0]["heading"] == "Moving weighted average (MWA)"


def test_new_tools_are_offered_to_every_reader(principals: dict[str, Principal]) -> None:
    names = {t.name for t in tools_for(principals["alpha.analyst"])}
    assert {"query_inventory", "search_knowledge"} <= names


# ------------------------------------------------------------------------------------------- S10 bug hunt
def test_how_many_items_counts_the_catalogue(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "How many items do we have?")
    assert [c["name"] for c in out["tool_calls"]] == ["inventory_summary"]


def test_data_questions_with_codes_never_fall_back_to_definitions(
    agent: AgentService, principals: dict[str, Principal]
) -> None:
    out = agent.chat(principals["alpha.admin"], "Why is warehouse 3100 so high?")
    assert "search_knowledge" not in [c["name"] for c in out["tool_calls"]]


def test_grouped_answers_name_the_leader_plainly(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "Which warehouse has the most stock?")
    assert "holds the most stock" in out["answer"]
    assert "The highest" not in out["answer"]
    assert "\u2014" not in out["answer"]  # no em dash in answer text
    assert out["grounding"]["passed"]


def test_definition_answers_do_not_repeat_the_heading(agent: AgentService, principals: dict[str, Principal]) -> None:
    out = agent.chat(principals["alpha.admin"], "How is inventory value calculated?")
    assert out["answer"].startswith("Inventory value is the sum")
