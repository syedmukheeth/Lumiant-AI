"""One connector per tenant — no connection object can reach two tenants' data."""

from __future__ import annotations

import threading
from pathlib import Path

from lumiant.connectors.base import Connector
from lumiant.connectors.duckdb_connector import DuckDBConnector
from lumiant.tenancy.registry import TenantRegistry


class ConnectorRegistry:
    def __init__(self, tenants: TenantRegistry, data_dir: Path) -> None:
        self._tenants = tenants
        self._data_dir = data_dir
        self._connectors: dict[str, Connector] = {}
        self._lock = threading.Lock()

    def get(self, tenant_id: str) -> Connector:
        with self._lock:
            connector = self._connectors.get(tenant_id)
            if connector is None:
                connector = self._create(tenant_id)
                self._connectors[tenant_id] = connector
            return connector

    def _create(self, tenant_id: str) -> Connector:
        conn = self._tenants.get(tenant_id).connection
        if conn.type == "duckdb" and conn.path:
            return DuckDBConnector(self._data_dir / conn.path)
        raise NotImplementedError(f"connector type '{conn.type}' is not implemented")

    def dispose_all(self) -> None:
        with self._lock:
            for connector in self._connectors.values():
                connector.dispose()
            self._connectors.clear()
