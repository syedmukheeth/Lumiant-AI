"""RAG v2: per-organisation knowledge index, cost-aware catalog chunks, the lasting vector cache and the embed command."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command

from lumiant.agent.knowledge_tools import KnowledgeArgs
from lumiant.agent.tools import TOOLS, ToolContext
from lumiant.audit.store import _alembic_config, run_migrations
from lumiant.auth.principal import Principal
from lumiant.canonical.catalog import CATALOG, Sensitivity
from lumiant.core.config import Settings
from lumiant.knowledge.cli import embed_static, run_embed
from lumiant.knowledge.index import Chunk, KnowledgeIndex, product_index, tenant_index
from lumiant.knowledge.vectors import (
    VectorCache,
    VectorMemory,
    decode,
    encode,
    split_embed_key,
    vector_key,
    write_static,
)
from lumiant.query.service import QueryService
from lumiant.tenancy.registry import TenantRegistry
from tests.helpers import app_db_url

COST_FIELDS = sorted(
    {f.name for ds in CATALOG.values() for f in ds.fields.values() if f.sensitivity is Sensitivity.COST}
)


def _tenant_chunks(index: KnowledgeIndex) -> list[Chunk]:
    return [c for c in index.chunks if c.id.startswith(("catalog#", "tenant#"))]


def _cost_field_mentions(text: str) -> list[str]:
    """Cost-sensitive field names as identifiers (`valuation_price`) or as entries of a catalog or hint list
    (`; valuation price: …`, `; valuation price of stock balance: …`)."""
    low = text.lower()
    found = []
    for name in COST_FIELDS:
        entry = rf"(?:^|[;.] ){re.escape(name.replace('_', ' '))}(?: of [a-z ]+)?:"
        if ("_" in name and name in low) or re.search(entry, low):
            found.append(name)
    return found


# ------------------------------------------------------------------------------------------ per-tenant index
def test_gamma_index_has_no_chunks_for_datasets_it_does_not_map(registry: TenantRegistry) -> None:
    gamma = registry.get("demo-gamma")
    for can_cost in (True, False):
        ids = {c.id for c in tenant_index(gamma, can_cost).chunks}
        assert {i for i in ids if i.startswith("catalog#")} == {f"catalog#{name}" for name in gamma.datasets}
        for name in set(CATALOG) - set(gamma.datasets):
            assert f"catalog#{name}" not in ids
        assert {"tenant#source_hints", "tenant#not_mapped"} <= ids
        for chunk in tenant_index(gamma, can_cost).search("lot batch expiry date receipt", k=10):
            assert chunk.chunk.id != "catalog#lot"
    # Another organisation that maps lots does get them.
    assert "catalog#lot" in {c.id for c in tenant_index(registry.get("demo-alpha"), True).chunks}


def test_not_mapped_chunk_names_missing_data_in_plain_words(registry: TenantRegistry) -> None:
    gamma = tenant_index(registry.get("demo-gamma"), True)
    missing = next(c for c in gamma.chunks if c.id == "tenant#not_mapped")
    assert missing.heading == "Not in this organisation's data"
    for phrase in ("stock movement history", "expiry dates", "purchase orders", "selling prices or margins", "profit"):
        assert phrase in missing.text
    assert "inventory_transaction" not in missing.text  # plain words, not dataset ids
    assert "No stock on hand" not in missing.text  # gamma maps stock balances
    hints = next(c for c in gamma.chunks if c.id == "tenant#source_hints")
    assert "SAP MB51" in hints.text
    assert "lot id of stock balance" in hints.text
    # Every dataset mapped: the chunk says so and still explains that profit needs sales data.
    delta = next(c for c in tenant_index(registry.get("demo-delta"), True).chunks if c.id == "tenant#not_mapped")
    assert delta.text.startswith("Every dataset")
    assert "profit" in delta.text
    assert "tenant#source_hints" not in {c.id for c in tenant_index(registry.get("demo-alpha"), True).chunks}


def test_role_without_cost_access_gets_no_cost_field_names(registry: TenantRegistry) -> None:
    for tenant in registry:
        for chunk in _tenant_chunks(tenant_index(tenant, False)):
            assert _cost_field_mentions(chunk.text) == [], (tenant.id, chunk.id)
            assert "selling prices" not in chunk.text
            assert "valuation prices" not in chunk.text
    # The same organisation with cost access sees them (the check above is not vacuous).
    with_cost = tenant_index(registry.get("demo-gamma"), True)
    stock = next(c for c in with_cost.chunks if c.id == "catalog#stock_balance")
    assert {"valuation_price", "stock_value", "source_value"} <= set(_cost_field_mentions(stock.text))
    no_cost = next(c for c in tenant_index(registry.get("demo-gamma"), False).chunks if c.id == "catalog#stock_balance")
    assert "currency:" not in no_cost.text  # the currency of a price the role cannot see is left out too
    assert "quantity: On-hand quantity" in no_cost.text


def test_search_knowledge_uses_the_callers_index(query_service: QueryService, principals: dict[str, Principal]) -> None:
    args = KnowledgeArgs(query="stock balance valuation price stock value fields")
    viewer = TOOLS["search_knowledge"].run(ToolContext(query_service, principals["gamma.viewer"]), args)
    texts = [s["text"] for s in viewer.data["sources"] if s["id"].startswith(("catalog#", "tenant#"))]
    assert texts, viewer.data["sources"]
    assert all(_cost_field_mentions(t) == [] for t in texts)
    admin = TOOLS["search_knowledge"].run(ToolContext(query_service, principals["gamma.admin"]), args)
    stock = next(s for s in admin.data["sources"] if s["id"] == "catalog#stock_balance")
    assert "valuation price:" in stock["text"]

    profit = TOOLS["search_knowledge"].run(
        ToolContext(query_service, principals["gamma.admin"]), KnowledgeArgs(query="Can you calculate our profit?")
    )
    assert {"inventory_levers#11", "tenant#not_mapped"} <= {s["id"] for s in profit.data["sources"]}
    lots = TOOLS["search_knowledge"].run(
        ToolContext(query_service, principals["gamma.admin"]), KnowledgeArgs(query="lot expiry date fields")
    )
    assert "catalog#lot" not in {s["id"] for s in lots.data["sources"]}


def test_tenant_index_is_cached_and_rebuilt_when_the_mapping_changes(registry: TenantRegistry) -> None:
    gamma = registry.get("demo-gamma")
    first = tenant_index(gamma, True)
    assert tenant_index(gamma, True) is first
    assert tenant_index(gamma, False) is not first
    edited = gamma.model_copy(update={"source_hints": {}})
    rebuilt = tenant_index(edited, True)
    assert rebuilt is not first
    assert "tenant#source_hints" not in {c.id for c in rebuilt.chunks}


def test_product_index_still_holds_the_whole_catalog() -> None:
    ids = {c.id for c in product_index().chunks}
    assert {f"catalog#{name}" for name in CATALOG} <= ids
    assert not any(i.startswith("tenant#") for i in ids)
    sections = [i for i in ids if i.startswith(("inventory_levers#", "analyst_capabilities#"))]
    assert 15 <= len(sections) <= 20


# ------------------------------------------------------------------------------------------ vector cache
class CountingEmbedder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def __call__(self, texts: list[str], task: str) -> list[list[float]]:
        self.calls.append((task, len(texts)))
        return [[float(len(t) % 7 + 1), float(sum(map(ord, t)) % 5 + 1), 1.0] for t in texts]

    def doc_calls(self) -> int:
        return sum(1 for task, _ in self.calls if task == "RETRIEVAL_DOCUMENT")


CHUNKS = [Chunk("a", "Doc", "Alpha", "apples and pears"), Chunk("b", "Doc", "Beta", "boats and ships")]


def test_vectors_are_compact_strings_keyed_by_model_dims_and_text() -> None:
    vec = [0.5, -1.25, 3.0]
    text = encode(vec)
    assert isinstance(text, str)
    assert len(text) == 16
    assert list(decode(text)) == vec
    assert vector_key("m", 3, "x") != vector_key("m", 4, "x") != vector_key("n", 3, "x")
    assert split_embed_key("gemini:gemini-embedding-001:768") == ("gemini:gemini-embedding-001", 768)
    assert split_embed_key("fake") == ("fake", 0)


def test_vector_cache_hit_avoids_the_embed_call(tmp_path: Path) -> None:
    url = app_db_url(tmp_path / "app.db")
    run_migrations(url)
    engine = sa.create_engine(url)
    try:
        embed = CountingEmbedder()
        cold = VectorCache(engine, static_path=None, memory=VectorMemory())
        assert KnowledgeIndex(CHUNKS).search("apples", embedder=embed, embed_key="fake:m:3", vectors=cold)
        assert embed.doc_calls() == 1
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT COUNT(*) FROM knowledge_vector")).scalar() == 2

        # Memory tier: same process, a fresh index.
        embed = CountingEmbedder()
        KnowledgeIndex(CHUNKS).search("apples", embedder=embed, embed_key="fake:m:3", vectors=cold)
        assert embed.doc_calls() == 0
        assert embed.calls == [("RETRIEVAL_QUERY", 1)]

        # App-DB tier: a new process (empty memory) reads the stored vectors instead of embedding again.
        embed = CountingEmbedder()
        warm = VectorCache(engine, static_path=None, memory=VectorMemory())
        hits = KnowledgeIndex(CHUNKS).search("apples", embedder=embed, embed_key="fake:m:3", vectors=warm)
        assert embed.doc_calls() == 0
        assert hits[0].chunk.id == "a"

        # Another model or size is another key, so nothing stale is served.
        embed = CountingEmbedder()
        KnowledgeIndex(CHUNKS).search("apples", embedder=embed, embed_key="fake:m:4", vectors=warm)
        assert embed.doc_calls() == 1
    finally:
        engine.dispose()


def test_committed_vectors_file_is_read_before_the_database(tmp_path: Path) -> None:
    path = tmp_path / "vectors.json"
    model, dims = "fake:m", 3
    write_static(path, {vector_key(model, dims, c.body): [1.0, 2.0, 3.0] for c in CHUNKS}, model, dims)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["encoding"] == "base64-float32-le"
    assert all(isinstance(v, str) for v in doc["vectors"].values())
    embed = CountingEmbedder()
    cache = VectorCache(None, static_path=path, memory=VectorMemory())
    KnowledgeIndex(CHUNKS).search("boats", embedder=embed, embed_key="fake:m:3", vectors=cache)
    assert embed.doc_calls() == 0
    # Vectors of the wrong size are ignored and embedded again.
    embed = CountingEmbedder()
    write_static(path, {vector_key(model, dims, c.body): [1.0, 2.0] for c in CHUNKS}, model, dims)
    KnowledgeIndex(CHUNKS).search(
        "boats", embedder=embed, embed_key="fake:m:3", vectors=VectorCache(None, path, VectorMemory())
    )
    assert embed.doc_calls() == 1


def test_a_broken_vector_store_never_breaks_search(tmp_path: Path) -> None:
    engine = sa.create_engine(f"sqlite:///{(tmp_path / 'no-tables.db').as_posix()}")  # never migrated
    try:
        embed = CountingEmbedder()
        cache = VectorCache(engine, static_path=tmp_path / "absent.json", memory=VectorMemory())
        hits = KnowledgeIndex(CHUNKS).search("boats", embedder=embed, embed_key="fake:m:3", vectors=cache)
        assert hits[0].chunk.id == "b"
        assert embed.doc_calls() == 1
    finally:
        engine.dispose()


def test_migration_0008_creates_and_drops_the_vector_table(tmp_path: Path) -> None:
    url = app_db_url(tmp_path / "app.db")
    run_migrations(url)
    engine = sa.create_engine(url)
    try:
        with engine.connect() as conn:
            assert conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar() == "0008"
            assert conn.execute(sa.text("SELECT COUNT(*) FROM knowledge_vector")).scalar() == 0
        columns = {c["name"]: c for c in sa.inspect(engine).get_columns("knowledge_vector")}
        assert set(columns) == {"text_hash", "model", "dims", "vector", "created_at"}
        assert isinstance(columns["vector"]["type"], sa.Text)
        command.downgrade(_alembic_config(url), "0007")
        assert "knowledge_vector" not in sa.inspect(engine).get_table_names()
        run_migrations(url)
        assert "knowledge_vector" in sa.inspect(engine).get_table_names()
    finally:
        engine.dispose()


# ------------------------------------------------------------------------------------------ embed command
def test_embed_command_refuses_without_a_key(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out = tmp_path / "vectors.json"
    assert run_embed(Settings(gemini_api_key=None), out=out) == 2
    assert "LUMIANT_GEMINI_API_KEY" in capsys.readouterr().err
    assert not out.exists()


def test_embed_static_writes_every_product_chunk(tmp_path: Path) -> None:
    out = tmp_path / "vectors.json"
    embed = CountingEmbedder()
    count = embed_static(embed, "fake:m:3", out)
    assert count == len({c.body for c in product_index().chunks})
    assert all(task == "RETRIEVAL_DOCUMENT" for task, _ in embed.calls)
    later = CountingEmbedder()
    cache = VectorCache(None, static_path=out, memory=VectorMemory())
    KnowledgeIndex(product_index().chunks).search("carrying cost", embedder=later, embed_key="fake:m:3", vectors=cache)
    assert later.doc_calls() == 0
