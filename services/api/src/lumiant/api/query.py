from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from lumiant.auth.deps import get_container, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.query.plan import QueryPlan

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", dependencies=[Depends(require_csrf)])
def run_query(
    plan: QueryPlan,
    principal: Annotated[Principal, Depends(require(Permission.QUERY_RUN))],
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    """Run a structured QueryPlan. The same engine the dashboard and (later) the AI agent use."""
    return container.query.run_plan(plan, principal, action="query").payload()
