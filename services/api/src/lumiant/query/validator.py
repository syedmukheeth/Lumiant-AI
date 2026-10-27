"""Plan validation: the authoritative checks between any caller (UI, analyses, future AI) and the data.

Rules and error codes are documented in docs/02-architecture/QUERY_ENGINE.md §2. Scope filters are
injected here, *after* the caller's plan, so no caller can widen its own scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from lumiant.auth.permissions import Permission
from lumiant.auth.principal import Principal
from lumiant.canonical.catalog import CATALOG, DatasetDef, FieldDef, FieldRole, FieldType, Sensitivity
from lumiant.core.errors import AppError
from lumiant.mapping.resolver import TenantMapping
from lumiant.query.plan import COMPARISON_OPS, Agg, AnyOf, Filter, Op, QueryPlan
from lumiant.tenancy.models import Policies


class PlanRejectedError(AppError):
    pass


def reject(code: str, message: str, status: int = 400) -> PlanRejectedError:
    return PlanRejectedError(code, message, status)


@dataclass(frozen=True)
class FieldRef:
    ref: str
    join: str | None
    dataset: str
    fdef: FieldDef


@dataclass(frozen=True)
class AppliedFilter:
    field: FieldRef
    op: Op
    value: Any
    origin: Literal["user", "scope"]


@dataclass(frozen=True)
class FilterGroup:
    any_of: tuple[AppliedFilter, ...]


@dataclass(frozen=True)
class MeasureSpec:
    field: FieldRef
    agg: Agg
    alias: str
    out_type: FieldType


@dataclass(frozen=True)
class HavingSpec:
    measure: MeasureSpec
    op: Op
    value: Any


@dataclass(frozen=True)
class OrderSpec:
    name: str
    target: FieldRef | MeasureSpec
    descending: bool


@dataclass(frozen=True)
class OutputColumn:
    name: str
    type: FieldType
    kind: Literal["dimension", "measure"]
    sensitivity: Sensitivity


@dataclass(frozen=True)
class ValidatedPlan:
    dataset: DatasetDef
    dimensions: tuple[FieldRef, ...]
    measures: tuple[MeasureSpec, ...]
    filters: tuple[AppliedFilter | FilterGroup, ...]
    having: tuple[HavingSpec, ...]
    order_by: tuple[OrderSpec, ...]
    limit: int
    offset: int
    joins: tuple[str, ...]
    auto_grouped: tuple[str, ...]

    @property
    def aggregate(self) -> bool:
        return bool(self.measures)

    @property
    def columns(self) -> list[OutputColumn]:
        cols = [OutputColumn(d.ref, d.fdef.type, "dimension", d.fdef.sensitivity) for d in self.dimensions]
        cols += [OutputColumn(m.alias, m.out_type, "measure", m.field.fdef.sensitivity) for m in self.measures]
        return cols

    def referenced_fields(self) -> list[FieldRef]:
        refs = [*self.dimensions, *(m.field for m in self.measures)]
        for f in self.filters:
            refs += [g.field for g in f.any_of] if isinstance(f, FilterGroup) else [f.field]
        seen: dict[str, FieldRef] = {}
        for r in refs:
            seen.setdefault(r.ref, r)
        return list(seen.values())


_ORDERABLE = (FieldType.INTEGER, FieldType.DECIMAL, FieldType.DATE, FieldType.DATETIME)
_MAX_TEXT = 200


class PlanValidator:
    def __init__(self, mapping: TenantMapping, policies: Policies) -> None:
        self.mapping = mapping
        self.policies = policies

    # ---------------------------------------------------------------------------------- entry
    def validate(self, plan: QueryPlan, principal: Principal) -> ValidatedPlan:
        if principal.tenant_id != self.mapping.tenant.id:  # defensive: callers pass the tenant's mapping
            raise reject("forbidden", "Not allowed.", 403)
        dataset = self._dataset(plan.dataset)
        joins: list[str] = []

        def resolve(ref: str) -> FieldRef:
            fref = self._resolve(dataset, ref)
            if fref.join and fref.join not in joins:
                joins.append(fref.join)
            return fref

        dims = [resolve(d) for d in plan.dimensions]
        measures = [self._measure(resolve(m.field), m.agg, m.name) for m in plan.measures]
        aggregate = bool(measures)
        if aggregate:
            for d in dims:
                if d.fdef.role is FieldRole.MEASURE:
                    raise reject("invalid_dimension", f"'{d.ref}' is a measure and cannot be a grouping.")

        filters: list[AppliedFilter | FilterGroup] = []
        for f in plan.filters:
            if isinstance(f, AnyOf):
                filters.append(FilterGroup(tuple(self._filter(resolve(g.field), g, principal) for g in f.any)))
            else:
                filters.append(self._filter(resolve(f.field), f, principal))

        # Safety rails: amounts never aggregate or display without their currency / unit.
        auto: list[str] = []
        dim_refs = {d.ref for d in dims}

        def companion(fref: FieldRef, name: str | None) -> None:
            if name is None:
                return
            ref = f"{fref.join}.{name}" if fref.join else name
            if ref in dim_refs:
                return
            if self.mapping.field(fref.dataset, name) is None:
                raise reject(
                    "field_not_available",
                    f"'{fref.ref}' cannot be used because its {name} is not mapped for this tenant.",
                )
            dims.append(resolve(ref))
            dim_refs.add(ref)
            auto.append(ref)

        if aggregate:
            for m in measures:
                if m.agg not in (Agg.COUNT, Agg.COUNT_DISTINCT):
                    companion(m.field, m.field.fdef.currency_field)
                    companion(m.field, m.field.fdef.unit_field)
        else:
            for d in list(dims):
                companion(d, d.fdef.currency_field)
                companion(d, d.fdef.unit_field)

        used = [*dims, *(m.field for m in measures)]
        for applied in filters:
            used += [g.field for g in applied.any_of] if isinstance(applied, FilterGroup) else [applied.field]
        self._check_sensitive(used, principal)

        scope_filters = self._scope(dataset, principal)
        having = [self._having(h.measure, h.op, h.value, measures) for h in plan.having]
        order = self._order(plan, dims, measures)
        limit = plan.limit if plan.limit is not None else self.policies.default_rows
        if limit > self.policies.max_rows:
            raise reject("limit_exceeded", f"At most {self.policies.max_rows} rows can be requested at once.")

        return ValidatedPlan(
            dataset=dataset,
            dimensions=tuple(dims),
            measures=tuple(measures),
            filters=(*filters, *scope_filters),
            having=tuple(having),
            order_by=tuple(order),
            limit=limit,
            offset=plan.offset,
            joins=tuple(joins),
            auto_grouped=tuple(auto),
        )

    # ---------------------------------------------------------------------------------- resolution
    def _dataset(self, name: str) -> DatasetDef:
        ds = CATALOG.get(name)
        if ds is None or not self.mapping.is_mapped(name):
            raise reject("dataset_not_available", f"Dataset '{name}' is not available for this tenant.")
        return ds

    def _resolve(self, dataset: DatasetDef, ref: str) -> FieldRef:
        join_name, _, name = ref.rpartition(".")
        if not join_name:
            fdef = self.mapping.field(dataset.name, name)
            if fdef is None:
                raise reject("field_not_available", f"Field '{ref}' is not available in '{dataset.name}'.")
            return FieldRef(ref, None, dataset.name, fdef)
        join = dataset.joins.get(join_name)
        if join is None:
            raise reject("join_not_allowed", f"'{join_name}' is not an approved link from '{dataset.name}'.")
        if not self.mapping.is_mapped(join.dataset):
            raise reject("dataset_not_available", f"Dataset '{join.dataset}' is not available for this tenant.")
        for local, remote in join.on:
            if self.mapping.field(dataset.name, local) is None or self.mapping.field(join.dataset, remote) is None:
                raise reject("join_not_allowed", f"The link to '{join_name}' is not mapped for this tenant.")
        fdef = self.mapping.field(join.dataset, name)
        if fdef is None:
            raise reject("field_not_available", f"Field '{ref}' is not available.")
        return FieldRef(ref, join_name, join.dataset, fdef)

    def _measure(self, fref: FieldRef, agg: Agg, alias: str) -> MeasureSpec:
        fdef = fref.fdef
        if agg in (Agg.SUM, Agg.AVG):
            if not (fdef.numeric and fdef.role is FieldRole.MEASURE):
                raise reject("invalid_aggregation", f"'{fref.ref}' cannot be summed or averaged.")
            out = FieldType.DECIMAL if agg is Agg.AVG else fdef.type
        elif agg in (Agg.MIN, Agg.MAX):
            if fdef.type not in _ORDERABLE:
                raise reject("invalid_aggregation", f"'{fref.ref}' has no minimum or maximum.")
            out = fdef.type
        else:
            out = FieldType.INTEGER
        return MeasureSpec(fref, agg, alias, out)

    # ---------------------------------------------------------------------------------- filters
    def _filter(self, fref: FieldRef, f: Filter, principal: Principal) -> AppliedFilter:
        ftype = fref.fdef.type
        op, raw = f.op, f.value
        if op in (Op.IS_NULL, Op.IS_NOT_NULL):
            if raw is not None:
                raise reject("invalid_filter", f"'{op}' takes no value.")
            return AppliedFilter(fref, op, None, "user")
        if raw is None:
            raise reject("invalid_filter", f"'{op}' on '{fref.ref}' needs a value.")
        if op is Op.CONTAINS and ftype is not FieldType.STRING:
            raise reject("invalid_filter", f"'contains' only works on text fields ('{fref.ref}').")
        if op in (Op.LT, Op.LTE, Op.GT, Op.GTE, Op.BETWEEN) and ftype not in _ORDERABLE:
            raise reject("invalid_filter", f"'{op}' does not apply to '{fref.ref}'.")
        if op in (Op.IN, Op.NOT_IN, Op.BETWEEN):
            if not isinstance(raw, list) or not raw:
                raise reject("invalid_filter", f"'{op}' needs a non-empty list.")
            if op is Op.BETWEEN and len(raw) != 2:
                raise reject("invalid_filter", "'between' needs exactly two values.")
            value: Any = [coerce(v, ftype, fref.ref) for v in raw]
        else:
            if isinstance(raw, list):
                raise reject("invalid_filter", f"'{op}' takes a single value.")
            value = coerce(raw, ftype, fref.ref)
        if fref.fdef.scope_key and op in (Op.EQ, Op.IN) and not principal.scope.all:
            requested = value if isinstance(value, list) else [value]
            if any(not principal.scope.allows(str(v)) for v in requested):
                raise reject("forbidden_scope", "You do not have access to one or more of those warehouses.", 403)
        return AppliedFilter(fref, op, value, "user")

    def _check_sensitive(self, refs: list[FieldRef], principal: Principal) -> None:
        if principal.has(Permission.COST_READ):
            return
        for r in refs:
            if r.fdef.sensitivity is Sensitivity.COST:
                raise reject("forbidden_field", "Your role cannot view cost or value information.", 403)

    def _scope(self, dataset: DatasetDef, principal: Principal) -> list[AppliedFilter]:
        scope_field = dataset.scope_field
        if scope_field is None or principal.scope.all:
            return []
        if not principal.scope.ids:
            raise reject("forbidden_scope", "No warehouses are assigned to your account.", 403)
        fdef = self.mapping.field(dataset.name, scope_field)
        if fdef is None:  # cannot enforce scope → refuse rather than leak
            raise reject("dataset_not_available", f"Dataset '{dataset.name}' cannot be scoped for this tenant.")
        fref = FieldRef(scope_field, None, dataset.name, fdef)
        return [AppliedFilter(fref, Op.IN, sorted(principal.scope.ids), "scope")]

    def _having(self, alias: str, op: Op, raw: Any, measures: list[MeasureSpec]) -> HavingSpec:
        measure = next((m for m in measures if m.alias == alias), None)
        if measure is None:
            raise reject("invalid_having", f"'having' refers to unknown measure '{alias}'.")
        if op not in COMPARISON_OPS:
            raise reject("invalid_having", "'having' supports eq, ne, lt, lte, gt, gte.")
        return HavingSpec(measure, op, coerce(raw, measure.out_type, alias))

    def _order(self, plan: QueryPlan, dims: list[FieldRef], measures: list[MeasureSpec]) -> list[OrderSpec]:
        targets: dict[str, FieldRef | MeasureSpec] = {d.ref: d for d in dims}
        targets.update({m.alias: m for m in measures})
        if not plan.order_by:
            return [OrderSpec(d.ref, d, False) for d in dims]
        order = []
        for o in plan.order_by:
            target = targets.get(o.field)
            if target is None:
                raise reject("invalid_order", f"Can only sort by selected columns ('{o.field}').")
            order.append(OrderSpec(o.field, target, o.direction == "desc"))
        # Stable pagination: tie-break on the remaining dimensions.
        named = {o.name for o in order}
        order += [OrderSpec(d.ref, d, False) for d in dims if d.ref not in named]
        return order


def coerce(raw: Any, ftype: FieldType, ref: str) -> Any:
    def bad() -> PlanRejectedError:
        return reject("invalid_value", f"Value for '{ref}' is not a valid {ftype.value}.")

    if isinstance(raw, bool) and ftype is not FieldType.BOOLEAN:
        raise bad()
    try:
        match ftype:
            case FieldType.STRING:
                if not isinstance(raw, str) or len(raw) > _MAX_TEXT:
                    raise bad()
                return raw
            case FieldType.DECIMAL:
                value = Decimal(str(raw)) if isinstance(raw, (str, int)) else None
                if value is None or not value.is_finite():
                    raise bad()
                return value
            case FieldType.INTEGER:
                return int(raw)
            case FieldType.DATE:
                return raw if isinstance(raw, date) else date.fromisoformat(str(raw))
            case FieldType.DATETIME:
                return datetime.fromisoformat(str(raw))
            case FieldType.BOOLEAN:
                if not isinstance(raw, bool):
                    raise bad()
                return raw
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise bad() from exc
    raise bad()
