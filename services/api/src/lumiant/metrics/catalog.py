"""Metric catalog: named, versioned definitions shared by dashboard, chat and reports (value-add V1).

Every metric is `status="draft"` until the customer approves its definition (D-007). Changing a plan or
rule means bumping `version`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from lumiant.auth.permissions import Permission

VALUE_RULE = (
    "Sum of on-hand quantity × valuation price as provided by the source system, per currency. "
    "Stock lines without a valuation price are excluded and counted in a warning."
)


@dataclass(frozen=True)
class MetricDef:
    id: str
    version: int
    title: str
    description: str
    rule: str
    unit: Literal["currency", "count"]
    chart: Literal["kpi", "bar"]
    permissions: tuple[Permission, ...]
    plan: dict[str, Any]
    status: str = "draft"
    # Companion plan counting lines excluded from the metric (e.g. no valuation price).
    gap_plan: dict[str, Any] | None = None
    # Descriptive dimensions (e.g. a warehouse name) left out for tenants whose source does not provide them.
    optional_dims: tuple[str, ...] = ()

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "rule": self.rule,
            "unit": self.unit,
            "chart": self.chart,
            "status": self.status,
        }


_VALUE = [{"field": "stock_value", "agg": "sum", "alias": "value"}]
_VALUE_PERMS = (Permission.DASHBOARD_READ, Permission.COST_READ)
_MISSING_VALUATION = {
    "dataset": "stock_balance",
    "measures": [{"field": "item_id", "agg": "count", "alias": "lines"}],
    "filters": [
        {"field": "valuation_price", "op": "is_null"},
        {"field": "quantity", "op": "ne", "value": "0"},
    ],
}


def _value_by(metric_id: str, title: str, dims: list[str], optional: tuple[str, ...] = ()) -> MetricDef:
    return MetricDef(
        id=metric_id,
        version=1,
        title=title,
        description=f"{title}, per currency.",
        rule=VALUE_RULE,
        unit="currency",
        chart="bar",
        permissions=_VALUE_PERMS,
        plan={
            "dataset": "stock_balance",
            "dimensions": dims,
            "measures": _VALUE,
            "order_by": [{"field": "value", "direction": "desc"}],
            "limit": 50,
        },
        gap_plan=_MISSING_VALUATION,
        optional_dims=optional,
    )


METRICS: dict[str, MetricDef] = {
    m.id: m
    for m in (
        MetricDef(
            id="inventory_value_total",
            version=1,
            title="Inventory value",
            description="Total on-hand inventory value, per currency.",
            rule=VALUE_RULE,
            unit="currency",
            chart="kpi",
            permissions=_VALUE_PERMS,
            plan={"dataset": "stock_balance", "measures": _VALUE},
            gap_plan=_MISSING_VALUATION,
        ),
        _value_by(
            "inventory_value_by_warehouse",
            "Inventory value by warehouse",
            ["warehouse_id", "warehouse.name"],
            ("warehouse.name",),
        ),
        _value_by("inventory_value_by_abc", "Inventory value by ABC class (assigned)", ["item.abc_class"]),
        _value_by("inventory_value_by_item_group", "Inventory value by item group", ["item.item_group"]),
        _value_by("inventory_value_by_stage", "Inventory value by inventory stage", ["item.inventory_stage"]),
        MetricDef(
            id="items_in_stock",
            version=1,
            title="Items in stock",
            description="Distinct items with positive on-hand quantity.",
            rule="Count of distinct item ids with at least one stock line where quantity > 0.",
            unit="count",
            chart="kpi",
            permissions=(Permission.DASHBOARD_READ,),
            plan={
                "dataset": "stock_balance",
                "measures": [{"field": "item_id", "agg": "count_distinct", "alias": "items"}],
                "filters": [{"field": "quantity", "op": "gt", "value": "0"}],
            },
        ),
        MetricDef(
            id="stock_lines",
            version=1,
            title="Stock lines",
            description="Stock lines (item × warehouse × location × lot) with positive quantity.",
            rule="Count of stock balance lines where quantity > 0.",
            unit="count",
            chart="kpi",
            permissions=(Permission.DASHBOARD_READ,),
            plan={
                "dataset": "stock_balance",
                "measures": [{"field": "item_id", "agg": "count", "alias": "lines"}],
                "filters": [{"field": "quantity", "op": "gt", "value": "0"}],
            },
        ),
    )
}
