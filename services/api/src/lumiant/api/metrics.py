from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path

from lumiant.auth.deps import get_container, require
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container

router = APIRouter(prefix="/api/metrics", tags=["metrics"])
Reader = Annotated[Principal, Depends(require(Permission.DASHBOARD_READ))]


@router.get("")
def list_metrics(principal: Reader, container: Container = Depends(get_container)) -> dict[str, Any]:  # noqa: B008
    return {"metrics": [m.public() for m in container.metrics.visible(principal)]}


@router.get("/{metric_id}")
def get_metric(
    principal: Reader,
    metric_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{0,63}$")],
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    metric, result = container.metrics.run(metric_id, principal)
    return {"metric": metric.public(), **result.payload()}
