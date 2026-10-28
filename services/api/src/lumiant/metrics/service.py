"""Runs catalog metrics through the QueryService (same validation, scope, audit as everything else)."""

from __future__ import annotations

from lumiant.auth.principal import Principal
from lumiant.core.errors import ForbiddenError, NotFoundError
from lumiant.metrics.catalog import METRICS, MetricDef
from lumiant.query.plan import QueryPlan
from lumiant.query.results import QueryResult, ResultWarning
from lumiant.query.service import MetricRef, QueryService


class MetricsService:
    def __init__(self, query: QueryService) -> None:
        self.query = query

    def visible(self, principal: Principal) -> list[MetricDef]:
        return [m for m in METRICS.values() if all(principal.has(p) for p in m.permissions)]

    def run(self, metric_id: str, principal: Principal) -> tuple[MetricDef, QueryResult]:
        metric = METRICS.get(metric_id)
        if metric is None:
            raise NotFoundError("metric_not_found", "Unknown metric.")
        action = f"metric:{metric.id}"
        if not all(principal.has(p) for p in metric.permissions):
            self.query.record(principal, action, metric.plan["dataset"], "deny", "denied", reason="missing_permission")
            raise ForbiddenError("forbidden_field", "Your role cannot view this metric.")
        ref = MetricRef(metric.id, metric.version, metric.status, metric.rule)
        plan = dict(metric.plan)
        if metric.optional_dims:
            mapping = self.query.mapping(principal.tenant_id)
            plan["dimensions"] = [
                d for d in plan["dimensions"] if d not in metric.optional_dims or mapping.has_ref(plan["dataset"], d)
            ]
        result = self.query.run_plan(QueryPlan.model_validate(plan), principal, action=action, metric=ref)
        if metric.gap_plan is not None:
            gap = self.query.run_plan(QueryPlan.model_validate(metric.gap_plan), principal, action=f"{action}:gaps")
            excluded = int(gap.rows[0]["lines"]) if gap.rows else 0
            if excluded:
                result.warnings.append(
                    ResultWarning(
                        "missing_valuation_price",
                        f"{excluded} stock line(s) have no valuation price in the source and are not included.",
                    )
                )
                result.provenance["excluded_lines"] = excluded
        return metric, result
