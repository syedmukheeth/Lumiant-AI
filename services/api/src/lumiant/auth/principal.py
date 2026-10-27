"""The authenticated user context every data operation is checked against."""

from __future__ import annotations

from dataclasses import dataclass

from lumiant.auth.permissions import Permission
from lumiant.tenancy.models import DevUser, TenantConfig


@dataclass(frozen=True)
class WarehouseScope:
    all: bool
    ids: frozenset[str]

    def allows(self, warehouse_id: str) -> bool:
        return self.all or warehouse_id in self.ids

    def summary(self) -> dict[str, object]:
        return {"all_warehouses": self.all, "warehouses": sorted(self.ids)}


@dataclass(frozen=True)
class Principal:
    user_id: str
    display_name: str
    tenant_id: str
    roles: tuple[str, ...]
    permissions: frozenset[Permission]
    scope: WarehouseScope

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions


def principal_for_dev_user(tenant: TenantConfig, user: DevUser) -> Principal:
    permissions: set[Permission] = set()
    for role in user.roles:
        permissions.update(tenant.roles.get(role, []))
    all_warehouses = "*" in user.warehouses
    ids = set(tenant.warehouses_of_departments(user.departments))
    ids.update(w for w in user.warehouses if w != "*")
    if all_warehouses:
        ids = {w.id for w in tenant.warehouses}
    return Principal(
        user_id=user.username,
        display_name=user.display_name,
        tenant_id=tenant.id,
        roles=tuple(user.roles),
        permissions=frozenset(permissions),
        scope=WarehouseScope(all=all_warehouses, ids=frozenset(ids)),
    )
