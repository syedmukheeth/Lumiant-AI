from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lumiant.agent.context import MAX_HISTORY, ChatContext, HistoryTurn
from lumiant.agent.providers import SUGGESTIONS
from lumiant.auth.deps import get_container, rate_limit, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.core.errors import AppError
from lumiant.core.logging import request_id_var

log = logging.getLogger("lumiant.agent")
router = APIRouter(prefix="/api/agent", tags=["agent"])
Chatter = Annotated[Principal, Depends(require(Permission.CHAT_USE))]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Annotated[str, StringConstraints(min_length=2, max_length=500)]
    # What the user is looking at / selected (ADR-0010). Optional; narrows, never widens.
    context: ChatContext | None = None
    history: Annotated[list[HistoryTurn], Field(max_length=MAX_HISTORY)] = []


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Literal["up", "down"]
    reason: str | None = Field(default=None, max_length=40, pattern=r"^[A-Za-z0-9 _.,-]*$")


@router.get("/suggestions")
def suggestions(principal: Chatter) -> dict[str, Any]:
    return {"suggestions": SUGGESTIONS}


@router.post("/chat", dependencies=[Depends(require_csrf), Depends(rate_limit("chat"))])
def chat(
    body: ChatRequest, principal: Chatter, container: Annotated[Container, Depends(get_container)]
) -> dict[str, Any]:
    return container.agent.chat(principal, body.message, body.context, body.history)


def _sse(event: dict[str, Any]) -> str:
    return f"event: {event['type']}\ndata: {json.dumps(event, default=str, separators=(',', ':'))}\n\n"


@router.post("/chat/stream", dependencies=[Depends(require_csrf), Depends(rate_limit("chat"))])
def chat_stream(
    body: ChatRequest, principal: Chatter, container: Annotated[Container, Depends(get_container)]
) -> StreamingResponse:
    """The same pass as /chat, sent as server-sent events: `step`, `block`, then one `answer` (or `error`)."""
    request_id = request_id_var.get()

    def events() -> Iterator[str]:
        inner = container.agent.chat_events(principal, body.message, body.context, body.history)
        while True:
            # Each chunk runs in a fresh copy of the request context (thread pool), so restore the id every step.
            request_id_var.set(request_id)
            try:
                event = next(inner)
            except StopIteration:
                return
            except AppError as exc:
                yield _sse({"type": "error", "code": exc.code, "message": exc.message, "request_id": request_id})
                return
            except Exception:
                log.exception("chat_stream_failed")
                yield _sse(
                    {
                        "type": "error",
                        "code": "internal_error",
                        "message": "Something went wrong while answering. Please try again.",
                        "request_id": request_id,
                    }
                )
                return
            yield _sse(event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )


@router.post("/feedback", dependencies=[Depends(require_csrf)])
def feedback(
    body: FeedbackRequest, principal: Chatter, container: Annotated[Container, Depends(get_container)]
) -> dict[str, str]:
    container.agent.record_feedback(principal, body.rating, body.reason)
    return {"status": "recorded"}
