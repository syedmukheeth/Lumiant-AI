from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Path, Query, Response

from lumiant.auth.deps import get_container, rate_limit, require
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.container import Container

router = APIRouter(prefix="/api/reports", tags=["reports"])
Reader = Annotated[Principal, Depends(require(Permission.INVENTORY_READ))]
ReportId = Annotated[str, Path(pattern=r"^[a-z][a-z0-9_]{0,40}$")]
Days = Annotated[int | None, Query(ge=1, le=3650)]


def _params(days: int | None) -> dict[str, int]:
    return {} if days is None else {"days": days}


@router.get("")
def list_reports(principal: Reader, container: Annotated[Container, Depends(get_container)]) -> dict[str, Any]:
    return {
        "reports": [
            {"id": r.id, "title": r.title, "description": r.description, "params": list(r.params)}
            for r in container.reports.visible(principal)
        ],
        "can_export": principal.has(Permission.EXPORT_DATA),
    }


@router.get("/{report_id}")
def preview(
    principal: Reader, report_id: ReportId, container: Annotated[Container, Depends(get_container)], days: Days = None
) -> dict[str, Any]:
    return container.reports.build(report_id, principal, _params(days), limit=200)


@router.get("/{report_id}/export", dependencies=[Depends(rate_limit("export"))])
def export(
    principal: Reader,
    report_id: ReportId,
    container: Annotated[Container, Depends(get_container)],
    fmt: Annotated[Literal["csv", "xlsx"], Query(alias="format")] = "csv",
    days: Days = None,
) -> Response:
    body, media_type, name = container.reports.export(report_id, principal, _params(days), fmt)
    return Response(
        body,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
