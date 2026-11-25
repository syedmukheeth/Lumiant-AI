"""`search_knowledge`: retrieval over Lumiant's definitions, methods, policies and ERP terminology.

The retrieved text explains how something is defined or calculated; it never carries figures about the customer's
stock. Retrieved chunks are returned as a `sources` block so the answer can cite them.
"""

from __future__ import annotations

import re

from pydantic import Field

from lumiant.agent.tools import TOOLS, ToolContext, ToolDef, ToolOutput, _Args
from lumiant.auth.permissions import Permission
from lumiant.knowledge import product_index

MAX_SNIPPET = 600


class KnowledgeArgs(_Args):
    query: str = Field(min_length=2, max_length=200, description="What to look up, e.g. 'how is dormant stock defined'")


def _first_sentences(text: str, n: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


def search_knowledge(ctx: ToolContext, a: KnowledgeArgs) -> ToolOutput:
    hits = product_index().search(a.query, k=4, embedder=ctx.embedder, embed_key=ctx.embed_key)
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
    answer = f"{best.heading}: {_first_sentences(best.text)}"
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
        "terminology, how answers are checked and data is protected). Returns cited passages, never stock figures.",
        KnowledgeArgs,
        (Permission.INVENTORY_READ,),
        search_knowledge,
    ),
)
TOOLS.update({t.name: t for t in KNOWLEDGE_TOOLS})
