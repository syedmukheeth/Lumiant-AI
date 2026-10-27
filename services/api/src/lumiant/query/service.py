"""QueryService — the single execution path to customer data (docs/00-context/CONTEXT_FLOW.md §A1).

validate → compile → SQL guard → read-only connector → provenance → audit. Analyses reuse
`execute_select` so they get the same guard, timeout, error mapping and audit behaviour.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa

from lumiant.audit.store import AuditRecord, AuditStore
from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.connectors.base import ConnectorError, RawResult
from lumiant.connectors.registry import ConnectorRegistry
from lumiant.core.errors import AppError
from lumiant.core.logging import request_id_var
from lumiant.mapping.resolver import SourceObject, TenantMapping
from lumiant.query.compiler import compile_plan
from lumiant.query.plan import QueryPlan
from lumiant.query.results import Column, QueryResult, ResultWarning, to_json_value
from lumiant.query.sql_guard import SqlGuardError, check_sql
from lumiant.query.validator import (
    AppliedFilter,
    FilterGroup,
    PlanRejectedError,
    PlanValidator,
    ValidatedPlan,
)
from lumiant.tenancy.registry import TenantRegistry

log = logging.getLogger("lumiant.query")

_CONNECTOR_ERRORS = {
    "source_unavailable": (503, "The data source is currently unavailable."),
    "query_timeout": (504, "The query took too long and was stopped. Narrow the filters and try again."),
    "query_failed": (502, "The data source could not answer this query."),
}


@dataclass(frozen=True)
class MetricRef:
    id: str
    version: int
    status: str
    rule: str


@dataclass(frozen=True)
class TenantMeta:
    tenant_id: str
    display_name: str
    source_system: str
    synthetic: bool
    data_as_of: datetime | None
    stale: bool


class QueryService:
    META_TTL = timedelta(seconds=60)

    def __init__(self, tenants: TenantRegistry, connectors: ConnectorRegistry, audit: AuditStore) -> None:
        self.tenants = tenants
        self.connectors = connectors
        self.audit = audit
        self._mappings: dict[str, TenantMapping] = {}
        self._meta: dict[str, tuple[datetime, TenantMeta]] = {}
        self._lock = threading.Lock()

    # ---------------------------------------------------------------------------------- tenant info
    def mapping(self, tenant_id: str) -> TenantMapping:
        with self._lock:
            if tenant_id not in self._mappings:
                self._mappings[tenant_id] = TenantMapping(self.tenants.get(tenant_id))
            return self._mappings[tenant_id]

    def tenant_meta(self, tenant_id: str) -> TenantMeta:
        now = datetime.now(UTC)
        cached = self._meta.get(tenant_id)
        if cached and now - cached[0] < self.META_TTL:
            return cached[1]
        cfg = self.tenants.get(tenant_id)
        connector = self.connectors.get(tenant_id)
        marker = False
        as_of: datetime | None = None
        try:
            if connector.has_table(None, "_dataset_info"):
                info = sa.table("_dataset_info", sa.column("key"), sa.column("value"))
                stmt = sa.select(info.c.value).where(info.c.key == "synthetic")
                raw = connector.execute(stmt, fetch_limit=1, timeout_s=cfg.policies.query_timeout_s)
                marker = bool(raw.rows) and str(raw.rows[0][0]).lower() == "true"
            if cfg.freshness is not None:
                src = SourceObject.parse(cfg.freshness.object)
                fresh = sa.table(src.name, sa.column(cfg.freshness.column), schema=src.schema)
                stmt = sa.select(sa.func.max(fresh.c[cfg.freshness.column]))
                raw = connector.execute(stmt, fetch_limit=1, timeout_s=cfg.policies.query_timeout_s)
                value = raw.rows[0][0] if raw.rows else None
                if isinstance(value, datetime):
                    as_of = value if value.tzinfo else value.replace(tzinfo=UTC)
        except ConnectorError as exc:
            log.warning("tenant_meta_unavailable", extra={"tenant": tenant_id, "code": exc.code})
        stale = as_of is None or now - as_of > timedelta(hours=cfg.policies.stale_after_hours)
        meta = TenantMeta(cfg.id, cfg.display_name, cfg.source_system, cfg.synthetic or marker, as_of, stale)
        self._meta[tenant_id] = (now, meta)
        return meta

    # ---------------------------------------------------------------------------------- plans
    def validate(self, plan: QueryPlan, principal: Principal, *, action: str) -> ValidatedPlan:
        mapping = self.mapping(principal.tenant_id)
        try:
            return PlanValidator(mapping, mapping.tenant.policies).validate(plan, principal)
        except PlanRejectedError as exc:
            self.record(principal, action, plan.dataset, "deny", "denied", reason=exc.code)
            raise

    def run_plan(
        self,
        plan: QueryPlan,
        principal: Principal,
        *,
        action: str,
        metric: MetricRef | None = None,
        with_total: bool = False,
    ) -> QueryResult:
        vp = self.validate(plan, principal, action=action)
        mapping = self.mapping(principal.tenant_id)
        stmt = compile_plan(vp, mapping)
        fields = tuple(r.ref for r in vp.referenced_fields())
        raw = self.execute_select(
            principal, stmt, action=action, dataset=plan.dataset, fields=fields, fetch_limit=vp.limit + 1
        )
        total: int | None = None
        if with_total:
            count = self.execute_select(
                principal,
                compile_plan(vp, mapping, count_only=True),
                action=action,
                dataset=plan.dataset,
                fields=fields,
                fetch_limit=1,
                audit=False,
            )
            total = int(count.rows[0][0])
        truncated = len(raw.rows) > vp.limit
        rows = [dict(zip(raw.columns, r, strict=True)) for r in raw.rows[: vp.limit]]
        columns = [Column(c.name, c.type.value, c.kind) for c in vp.columns]
        meta = self.tenant_meta(principal.tenant_id)
        warnings = self._warnings(vp, meta, truncated)
        provenance = self.provenance(
            principal,
            mapping,
            meta,
            dataset=plan.dataset,
            source_datasets=[vp.dataset.name, *(vp.dataset.joins[j].dataset for j in vp.joins)],
            fields={r.ref: mapping.physical_ref(r.dataset, r.fdef.name) for r in vp.referenced_fields()},
            filters=list(vp.filters),
            auto_grouped=list(vp.auto_grouped),
            metric=metric,
            row_count=len(rows),
            truncated=truncated,
            duration_ms=raw.duration_ms,
            stmt=stmt,
        )
        page = {"offset": vp.offset, "limit": vp.limit, "total": total} if total is not None else None
        self.record(principal, action, plan.dataset, "allow", "ok", fields=fields, rows=len(rows), ms=raw.duration_ms)
        return QueryResult(columns, rows, provenance, warnings, truncated, page)

    # ---------------------------------------------------------------------------------- execution
    def execute_select(
        self,
        principal: Principal,
        stmt: sa.Select[Any],
        *,
        action: str,
        dataset: str,
        fields: tuple[str, ...] = (),
        fetch_limit: int,
        extra_tables: frozenset[str] = frozenset(),
        audit: bool = True,
    ) -> RawResult:
        mapping = self.mapping(principal.tenant_id)
        connector = self.connectors.get(principal.tenant_id)
        sql = self.render(stmt, connector.dialect)
        try:
            check_sql(sql, connector.dialect_name, mapping.physical_tables() | extra_tables)
        except SqlGuardError as exc:
            log.error("sql_guard_rejected", extra={"reason": exc.reason, "action": action})
            if audit:
                self.record(principal, action, dataset, "deny", "denied", reason="sql_guard", fields=fields)
            raise
        started = time.perf_counter()
        try:
            return connector.execute(stmt, fetch_limit=fetch_limit, timeout_s=mapping.tenant.policies.query_timeout_s)
        except ConnectorError as exc:
            status, message = _CONNECTOR_ERRORS.get(exc.code, (502, "The data source could not answer."))
            if audit:
                ms = round((time.perf_counter() - started) * 1000, 1)
                self.record(principal, action, dataset, "allow", "error", reason=exc.code, fields=fields, ms=ms)
            raise AppError(exc.code, message, status) from exc

    @staticmethod
    def render(stmt: sa.Select[Any], dialect: sa.engine.Dialect) -> str:
        return str(stmt.compile(dialect=dialect, compile_kwargs={"render_postcompile": True}))

    def record(
        self,
        principal: Principal,
        action: str,
        dataset: str | None,
        decision: str,
        status: str,
        *,
        reason: str | None = None,
        fields: tuple[str, ...] = (),
        rows: int | None = None,
        ms: float | None = None,
    ) -> None:
        self.audit.record(
            AuditRecord(
                tenant_id=principal.tenant_id,
                user_id=principal.user_id,
                action=action,
                decision=decision,
                status=status,
                dataset=dataset,
                fields=fields,
                reason_code=reason,
                row_count=rows,
                duration_ms=ms,
                request_id=request_id_var.get(),
            )
        )

    # ---------------------------------------------------------------------------------- provenance
    def provenance(
        self,
        principal: Principal,
        mapping: TenantMapping,
        meta: TenantMeta,
        *,
        dataset: str,
        source_datasets: list[str],
        fields: dict[str, str],
        filters: list[AppliedFilter | FilterGroup],
        auto_grouped: list[str],
        metric: MetricRef | None,
        row_count: int,
        truncated: bool,
        duration_ms: float,
        stmt: sa.Select[Any],
        rule: str | None = None,
    ) -> dict[str, Any]:
        user_filters: list[dict[str, Any]] = []
        injected: list[dict[str, Any]] = []
        for f in filters:
            if isinstance(f, FilterGroup):
                user_filters.append({"any": [_describe(g) for g in f.any_of]})
            elif f.origin == "scope":
                injected.append({**_describe(f), "reason": "warehouse_scope"})
            else:
                user_filters.append(_describe(f))
        sources: list[str] = []
        for ds in source_datasets:
            src = mapping.source_object(ds)
            if src not in sources:
                sources.append(src)
        prov: dict[str, Any] = {
            "tenant_id": principal.tenant_id,
            "source_system": meta.source_system,
            "synthetic": meta.synthetic,
            "dataset": dataset,
            "source_objects": sources,
            "fields": fields,
            "filters": {"user": user_filters, "injected": injected},
            "auto_grouped": auto_grouped,
            "data_as_of": meta.data_as_of.isoformat() if meta.data_as_of else None,
            "row_count": row_count,
            "truncated": truncated,
            "executed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "duration_ms": duration_ms,
        }
        if metric is not None:
            prov["metric"] = metric.__dict__
        if rule is not None:
            prov["rule"] = rule
        if principal.has(Permission.QUERY_VIEW_SQL):
            connector = self.connectors.get(principal.tenant_id)
            prov["sql"] = str(stmt.compile(dialect=connector.dialect))
        return prov

    @staticmethod
    def _warnings(vp: ValidatedPlan, meta: TenantMeta, truncated: bool) -> list[ResultWarning]:
        warnings: list[ResultWarning] = []
        if vp.auto_grouped:
            warnings.append(
                ResultWarning(
                    "auto_grouped",
                    f"Results are split by {', '.join(vp.auto_grouped)} so that amounts "
                    "in different currencies or units are never added together.",
                )
            )
        if truncated:
            warnings.append(ResultWarning("truncated", f"Only the first {vp.limit} rows are shown."))
        warnings += meta_warnings(meta)
        return warnings


def meta_warnings(meta: TenantMeta) -> list[ResultWarning]:
    if meta.data_as_of is None:
        return [ResultWarning("unknown_freshness", "The data timestamp is unknown.")]
    if meta.stale:
        return [
            ResultWarning("stale_data", f"Data was last refreshed {meta.data_as_of.isoformat(timespec='minutes')}.")
        ]
    return []


def _describe(f: AppliedFilter) -> dict[str, Any]:
    value = f.value
    value = [to_json_value(v) for v in value] if isinstance(value, list) else to_json_value(value)
    return {"field": f.field.ref, "op": f.op.value, "value": value}
