"""One connector per tenant — no connection object can reach two tenants' data."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from lumiant.connectors.base import Connector, ConnectorError, UnavailableConnector
from lumiant.connectors.duckdb_connector import DuckDBConnector
from lumiant.connectors.sql_connector import SqlConnector
from lumiant.tenancy.registry import TenantRegistry

log = logging.getLogger("lumiant.connectors")


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
        if conn.type == "sql" and conn.secret_ref:
            url = os.environ.get(conn.secret_ref.removeprefix("env:"), "")
            if not url:
                log.warning("source_not_configured", extra={"tenant": tenant_id, "secret_ref": conn.secret_ref})
                return UnavailableConnector()
            try:
                return SqlConnector(url)
            except ConnectorError as exc:
                log.warning("source_rejected", extra={"tenant": tenant_id, "code": exc.code})
                return UnavailableConnector()
        raise NotImplementedError(f"connector type '{conn.type}' is not implemented")

    def dispose_all(self) -> None:
        with self._lock:
            for connector in self._connectors.values():
                connector.dispose()
            self._connectors.clear()
