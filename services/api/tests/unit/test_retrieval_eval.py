"""Retrieval eval (RAG v2): BM25 recall@4 and MRR on `evals/retrieval.yaml`, held at the measured baseline.

recall@k: per question, the share of its expected chunks found in the top k (out of at most k), averaged.
MRR: per question, 1 / rank of the first expected chunk in the top 10 (0 when none), averaged.

Baselines measured when RAG v2 was built (keyword search only, no embeddings). A content or ranking change that
lowers them fails here; one that raises them should raise the baseline in the same change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
import yaml

from lumiant.core.config import BASE_DIR
from lumiant.knowledge.index import KnowledgeIndex, product_index, tenant_index
from lumiant.tenancy.registry import TenantRegistry

EVAL = yaml.safe_load((BASE_DIR / "evals" / "retrieval.yaml").read_text(encoding="utf-8"))
MRR_DEPTH = 10

BASELINE = {  # index -> (recall@4, MRR), floored to three decimals
    "product": (0.903, 0.913),
    "tenant": (0.948, 0.925),
    "tenant_no_cost": (0.937, 0.925),
}


@dataclass(frozen=True)
class Score:
    recall: float
    mrr: float
    questions: int


def score(index: KnowledgeIndex, questions: list[dict[str, Any]], k: int) -> Score:
    ids = {c.id for c in index.chunks}
    recall = rr = 0.0
    n = 0
    for item in questions:
        expected = [e for e in item["expect"] if e in ids]
        if not expected:
            continue
        n += 1
        ranked = [h.chunk.id for h in index.search(item["q"], k=MRR_DEPTH)]
        recall += sum(1 for e in expected if e in ranked[:k]) / min(len(expected), k)
        first = next((i for i, cid in enumerate(ranked) if cid in expected), None)
        rr += 1 / (first + 1) if first is not None else 0.0
    return Score(recall / n, rr / n, n)


def _index(name: str, registry: TenantRegistry) -> KnowledgeIndex:
    if name == "product":
        return product_index()
    return tenant_index(registry.get(EVAL["tenant"]), name == "tenant")


def test_eval_file_is_well_formed(registry: TenantRegistry) -> None:
    questions = EVAL["questions"]
    assert 35 <= len(questions) <= 50
    assert len({q["q"] for q in questions}) == len(questions)
    known = {c.id for c in product_index().chunks} | {c.id for c in _index("tenant", registry).chunks}
    for item in questions:
        assert item["expect"], item["q"]
        unknown = [e for e in item["expect"] if e not in known]
        assert not unknown, f"{item['q']}: unknown chunk ids {unknown} (a content section moved?)"


@pytest.mark.parametrize("name", list(BASELINE))
def test_retrieval_holds_the_baseline(name: str, registry: TenantRegistry) -> None:
    result = score(_index(name, registry), EVAL["questions"], EVAL["k"])
    recall, mrr = BASELINE[name]
    assert result.questions >= 40
    assert result.recall >= recall, f"{name}: recall@{EVAL['k']} {result.recall:.4f} < baseline {recall}"
    assert result.mrr >= mrr, f"{name}: MRR {result.mrr:.4f} < baseline {mrr}"


def test_business_questions_reach_the_playbook_and_the_missing_data(registry: TenantRegistry) -> None:
    gamma = _index("tenant", registry)
    top = {h.chunk.id for h in gamma.search("How can we free up cash tied up in inventory?")}
    assert {"inventory_levers#0", "inventory_levers#1"} <= top
    top = {h.chunk.id for h in gamma.search("Can you calculate our profit by product?")}
    assert {"inventory_levers#11", "tenant#not_mapped"} <= top
    top = {h.chunk.id for h in gamma.search("How do we reduce our carrying cost?")}
    assert "inventory_levers#2" in top
