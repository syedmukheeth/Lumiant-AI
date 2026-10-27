from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from lumiant.auth.deps import get_container
from lumiant.container import Container

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness(container: Container = Depends(get_container)) -> JSONResponse:  # noqa: B008
    """Unauthenticated, so it reveals only counts — never tenant ids or error details."""
    healthy = sum(1 for tenant_id in container.tenants.ids() if container.connectors.get(tenant_id).health())
    total = len(container.tenants.ids())
    status = "ok" if healthy == total else "degraded"
    return JSONResponse(
        {"status": status, "sources_available": healthy, "sources_total": total},
        status_code=200 if status == "ok" else 503,
    )
