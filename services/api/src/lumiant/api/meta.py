from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from lumiant.auth.deps import current_principal, get_container
from lumiant.auth.principal import Principal
from lumiant.container import Container
from lumiant.query.service import meta_warnings

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/tenant")
def tenant_meta(
    principal: Principal = Depends(current_principal),  # noqa: B008
    container: Container = Depends(get_container),  # noqa: B008
) -> dict[str, Any]:
    meta = container.query.tenant_meta(principal.tenant_id)
    policies = container.tenants.get(principal.tenant_id).policies
    return {
        "tenant_id": meta.tenant_id,
        "display_name": meta.display_name,
        "source_system": meta.source_system,
        "synthetic": meta.synthetic,
        "data_classification": meta.data_classification,
        "data_as_of": meta.data_as_of.isoformat() if meta.data_as_of else None,
        "stale": meta.stale,
        "stale_after_hours": policies.stale_after_hours,
        "max_rows": policies.max_rows,
        "warnings": [w.__dict__ for w in meta_warnings(meta)],
    }
