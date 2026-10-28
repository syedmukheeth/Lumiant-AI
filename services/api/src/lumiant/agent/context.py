"""What the screen tells the agent: the page, its filters and the elements the user selected to analyze (ADR-0010).

Context is a hint from the browser, never an authority. It can only pre-fill or NARROW tool arguments; every value
still goes through the typed tools, the query validator and server-side scope injection. Warehouse and item ids are
checked against what the principal can see before anything runs, and labels are display text only: they are never
used as filter values, never added to the grounding evidence and never shown to a model.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Ids and filter values: printable, no control characters, short.
Code = Annotated[str, StringConstraints(min_length=1, max_length=64, pattern=r"^[^\x00-\x1f\x7f]+$")]
Label = Annotated[str, StringConstraints(max_length=120, pattern=r"^[^\x00-\x1f\x7f]*$")]
ToolName = Annotated[str, StringConstraints(pattern=r"^[a-z_]{1,40}$")]
ArgValue = Code | int | None

SelectionKind = Literal[
    "warehouse", "location", "item", "item_group", "stage", "abc", "stock_status", "metric", "insight"
]
MAX_SELECTIONS = 5
MAX_HISTORY = 6


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Selection(_Strict):
    kind: SelectionKind
    id: Code
    label: Label | None = None


class ContextFilters(_Strict):
    warehouse_id: Code | None = None
    item_group: Code | None = None
    stage: Code | None = None
    stock_status: Code | None = None


class ChatContext(_Strict):
    page: Annotated[str, StringConstraints(pattern=r"^[a-z-]{1,24}$")] | None = None
    widget: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_.:-]{1,64}$")] | None = None
    filters: ContextFilters = ContextFilters()
    selections: Annotated[list[Selection], Field(max_length=MAX_SELECTIONS)] = []


class HistoryTurn(_Strict):
    """A previous question and the tool that answered it. No result data: follow-ups re-run tools, they never reuse
    numbers from an earlier answer."""

    question: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    tool: ToolName | None = None
    args: Annotated[dict[ToolName, ArgValue | list[Code]], Field(max_length=8)] = {}


__all__ = ["ChatContext", "ContextFilters", "HistoryTurn", "Selection"]
