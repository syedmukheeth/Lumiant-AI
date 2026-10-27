from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from lumiant.analyses.below_reorder import BelowReorderFilters, run_below_reorder
from lumiant.analyses.risks import run_abc, run_cost_comparison, run_data_quality, run_dormant, run_expiring
from lumiant.auth.deps import get_container, require
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container

router = APIRouter(prefix="/api/analyses", tags=["analyses"])
Reader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ))]
CostReader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ, Permission.COST_READ))]
Page = Annotated[int, Query(ge=1, le=200)]
Code = Annotated[str, Query(min_length=1, max_length=64)]


@router.get("/excess-stock")
def excess_stock(
    principal: Reader,
    container: Container = Depends(get_container),  # noqa: B008
    warehouse: Annotated[list[str] | None, Query(max_length=50)] = None,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Page = 50,
) -> dict[str, Any]:
    filters = BelowReorderFilters(warehouses=tuple(warehouse or ()))
    return run_below_reorder(container.query, principal, filters, limit=limit, offset=offset, mode="excess").payload()


@router.get("/dormant")
def dormant(
    principal: Reader,
    container: Container = Depends(get_container),  # noqa: B008
    days: Annotated[int, Query(ge=1, le=3650)] = 270,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
    limit: Page = 50,
) -> dict[str, Any]:
    return run_dormant(container.query, principal, days=days, limit=limit, offset=offset).payload()


@router.get("/expiring-lots")
def expiring_lots(
    principal: Reader,
    container: Container = Depends(get_container),  # noqa: B008
    days: Annotated[int, Query(ge=0, le=3650)] = 60,
    limit: Page = 100,
) -> dict[str, Any]:
    return run_expiring(container.query, principal, days=days, limit=limit).payload()


@router.get("/data-quality")
def data_quality(principal: Reader, container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    return run_data_quality(container.query, principal)


@router.get("/abc")
def abc(
    principal: CostReader,
    a: Annotated[Decimal, Query(gt=0, lt=1)],
    b: Annotated[Decimal, Query(gt=0, le=1)],
    currency: Annotated[str | None, Query(pattern=r"^[A-Z]{3}$")] = None,
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    return run_abc(container.query, principal, a_cutoff=a, b_cutoff=b, currency=currency)


@router.get("/cost-comparison")
def cost_comparison(
    principal: CostReader,
    item_id: Code,
    warehouse_id: Code,
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    return run_cost_comparison(container.query, principal, item_id=item_id, warehouse_id=warehouse_id)
