"""`search_knowledge`: retrieval over Lumiant's definitions, methods, policies, ERP terminology, inventory practice
and what this organisation's connected data does and does not contain.

The retrieved text explains how something is defined or calculated; it never carries figures about the customer's
stock. Each search runs on the organisation's own index (RAG v2, `knowledge.tenant_index`): its mapped datasets and
fields only, cost-sensitive fields only for roles with cost access. Retrieved chunks are returned as a `sources` block
so the answer can cite them.
"""

from __future__ import annotations

import re

from pydantic import Field

from lumiant.agent.tools import TOOLS, ToolContext, ToolDef, ToolOutput, _Args
from lumiant.auth.permissions import Permission
from lumiant.knowledge import KnowledgeIndex, tenant_index
from lumiant.knowledge.vectors import VectorCache, vector_cache

MAX_SNIPPET = 600


class KnowledgeArgs(_Args):
    query: str = Field(min_length=2, max_length=200, description="What to look up, e.g. 'how is dormant stock defined'")


def _first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


def knowledge_index(ctx: ToolContext) -> KnowledgeIndex:
    """The caller's organisation index; cost-sensitive catalog fields only when the principal may read cost."""
    tenant = ctx.query.mapping(ctx.principal.tenant_id).tenant
    return tenant_index(tenant, ctx.principal.has(Permission.COST_READ))


def knowledge_vectors(ctx: ToolContext) -> VectorCache:
    """The lasting vector cache, backed by the app database the query service audits to."""
    audit = getattr(ctx.query, "audit", None)
    return vector_cache(getattr(audit, "engine", None))


def search_knowledge(ctx: ToolContext, a: KnowledgeArgs) -> ToolOutput:
    vectors = knowledge_vectors(ctx) if ctx.embedder is not None else None
    hits = knowledge_index(ctx).search(a.query, k=4, embedder=ctx.embedder, embed_key=ctx.embed_key, vectors=vectors)
    if not hits:
        return ToolOutput(
            "search_knowledge",
            "Knowledge",
            "I found nothing in Lumiant's definitions about that.",
            data={"sources": []},
        )
    sources = [
        {
            "id": h.chunk.id,
            "source": h.chunk.source,
            "heading": h.chunk.heading,
            "text": h.chunk.text[:MAX_SNIPPET],
        }
        for h in hits
    ]
    best = hits[0].chunk
    lead = _first_sentences(best.text)
    # "Inventory value: Inventory value is …" reads twice; only name the section when the text does not.
    first_word = best.heading.split()[0].lower()
    answer = lead if lead.lower().startswith(first_word) else f"{best.heading}: {lead}"
    block = {"type": "sources", "title": "From Lumiant's definitions", "items": sources}
    return ToolOutput(
        "search_knowledge",
        "Definitions",
        answer,
        [block],
        data={"sources": sources},
        follow_ups=[],
    )


KNOWLEDGE_TOOLS = (
    ToolDef(
        "search_knowledge",
        "Look up how Lumiant defines or calculates something (metrics, costing methods, planning terms, ERP "
        "terminology, how answers are checked and data is protected), inventory practice (freeing cash, carrying "
        "cost, turns, excess and idle stock, expiry, safety stock, reorder tuning, what a profit analysis needs), "
        "what the Analyst can answer, and which data this organisation has connected or is missing. Returns cited "
        "passages, never stock figures.",
        KnowledgeArgs,
        (Permission.INVENTORY_READ,),
        search_knowledge,
    ),
)
TOOLS.update({t.name: t for t in KNOWLEDGE_TOOLS})
