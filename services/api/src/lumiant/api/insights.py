from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from lumiant.auth.deps import get_container, require
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container

router = APIRouter(prefix="/api/insights", tags=["insights"])
Reader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ))]


@router.get("")
def insight_feed(
    principal: Reader,
    container: Annotated[Container, Depends(get_container)],
    fresh: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    return container.insights.feed(principal, fresh=fresh)
