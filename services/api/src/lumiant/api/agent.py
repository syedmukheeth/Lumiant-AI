from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from lumiant.agent.providers import SUGGESTIONS
from lumiant.auth.deps import get_container, rate_limit, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container

router = APIRouter(prefix="/api/agent", tags=["agent"])
Chatter = Annotated[Principal, Depends(require(Permission.CHAT_USE))]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Annotated[str, StringConstraints(min_length=2, max_length=500)]


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
    return container.agent.chat(principal, body.message)


@router.post("/feedback", dependencies=[Depends(require_csrf)])
def feedback(
    body: FeedbackRequest, principal: Chatter, container: Annotated[Container, Depends(get_container)]
) -> dict[str, str]:
    container.agent.record_feedback(principal, body.rating, body.reason)
    return {"status": "recorded"}
