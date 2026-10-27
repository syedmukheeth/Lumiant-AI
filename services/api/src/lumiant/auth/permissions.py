"""Permission vocabulary. Roles map to these per tenant (see docs/01-product/ROLES_PERMISSIONS.md)."""

from enum import StrEnum


class Permission(StrEnum):
    DASHBOARD_READ = "dashboard:read"
    INVENTORY_READ = "inventory:read"
    COST_READ = "cost:read"
    QUERY_RUN = "query:run"
    QUERY_VIEW_SQL = "query:view_sql"
    AUDIT_READ = "audit:read"
    ADMIN_TENANT = "admin:tenant"
