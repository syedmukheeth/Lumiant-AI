"""Planning endpoints (read-only recommendations; docs/MRP_AND_ORDER_FULFILMENT.md)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from lumiant.auth.deps import get_container, require, require_csrf
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.planning.service import POLICIES, PlanningService

router = APIRouter(prefix="/api/planning", tags=["planning"])
Reader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ))]
CostReader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ, Permission.COST_READ))]
Code = Annotated[str, Query(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.\-/ ]+$")]
AsOf = Annotated[date | None, Query(description="Planning date (default today), for what-if runs")]
Qty = Annotated[Decimal, Query(gt=0, le=Decimal("1e12"))]


def _svc(container: Container) -> PlanningService:
    return PlanningService(container.query)


@router.get("/fulfilment")
def fulfilment(
    principal: Reader,
    container: Container = Depends(get_container),  # noqa: B008
    order: Code | None = None,
    as_of: AsOf = None,
) -> dict[str, Any]:
    return _svc(container).fulfilment(principal, order_id=order, today=as_of)


@router.get("/material-plan")
def material_plan(
    principal: Reader,
    container: Container = Depends(get_container),  # noqa: B008
    item: Code | None = None,
    as_of: AsOf = None,
) -> dict[str, Any]:
    return _svc(container).material_plan(principal, item_id=item, today=as_of)


@router.get("/bom")
def bom(
    principal: Reader,
    item: Code,
    qty: Qty = Decimal(1),
    container: Container = Depends(get_container),  # noqa: B008
    as_of: AsOf = None,
) -> dict[str, Any]:
    return _svc(container).bom(principal, item, qty, as_of)


@router.get("/suppliers")
def suppliers(
    principal: CostReader,
    item: Code,
    qty: Qty,
    container: Container = Depends(get_container),  # noqa: B008
    need_date: date | None = None,
    policy: Annotated[str, Query(pattern="^(" + "|".join(POLICIES) + ")$")] = "balanced",
    as_of: AsOf = None,
) -> dict[str, Any]:
    return _svc(container).suppliers(principal, item, qty, need_date=need_date, policy=policy, today=as_of)


@router.get("/duplicates")
def duplicates(principal: Reader, container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    return _svc(container).duplicates(principal)


@router.get("/lifecycle")
def lifecycle(principal: Reader, container: Container = Depends(get_container), as_of: AsOf = None) -> dict[str, Any]:  # noqa: B008
    return _svc(container).lifecycle(principal, as_of)


class AssessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=1000)


@router.post("/assess", dependencies=[Depends(require_csrf)])
def assess(body: AssessRequest, principal: Reader, container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    return _svc(container).assess(principal, body.question)
