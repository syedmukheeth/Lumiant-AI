"""QueryPlan — the only input shape that can reach customer data (docs/02-architecture/QUERY_ENGINE.md §1).

Floats are rejected on purpose: decimals travel as strings so no precision is lost before validation.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StringConstraints, model_validator

FieldRefStr = Annotated[str, StringConstraints(pattern=r"^[a-z_][a-z0-9_]*(\.[a-z_][a-z0-9_]*)?$", max_length=80)]
AliasStr = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,40}$")]
ScalarStr = Annotated[str, StringConstraints(max_length=200)]
Scalar = ScalarStr | StrictInt | StrictBool


class Agg(StrEnum):
    SUM = "sum"
    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    MIN = "min"
    MAX = "max"
    AVG = "avg"


class Op(StrEnum):
    EQ = "eq"
    NE = "ne"
    IN = "in"
    NOT_IN = "not_in"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    BETWEEN = "between"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    CONTAINS = "contains"


COMPARISON_OPS = frozenset({Op.EQ, Op.NE, Op.LT, Op.LTE, Op.GT, Op.GTE})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Measure(_Strict):
    field: FieldRefStr
    agg: Agg
    alias: AliasStr | None = None

    @property
    def name(self) -> str:
        return self.alias or f"{self.agg.value}_{self.field.replace('.', '_')}"


class Filter(_Strict):
    field: FieldRefStr
    op: Op
    value: Scalar | Annotated[list[Scalar], Field(max_length=500)] | None = None


class AnyOf(_Strict):
    """Rows matching at least one of the filters (e.g. a search across code and description)."""

    any: Annotated[list[Filter], Field(min_length=1, max_length=5)]


class Having(_Strict):
    measure: AliasStr
    op: Op
    value: ScalarStr | StrictInt


class OrderBy(_Strict):
    field: Annotated[str, StringConstraints(max_length=80)]
    direction: Literal["asc", "desc"] = "asc"


class QueryPlan(_Strict):
    dataset: Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]{0,40}$")]
    dimensions: Annotated[list[FieldRefStr], Field(max_length=20)] = []
    measures: Annotated[list[Measure], Field(max_length=20)] = []
    filters: Annotated[list[Filter | AnyOf], Field(max_length=30)] = []
    having: Annotated[list[Having], Field(max_length=10)] = []
    order_by: Annotated[list[OrderBy], Field(max_length=5)] = []
    limit: Annotated[int, Field(ge=1)] | None = None
    offset: Annotated[int, Field(ge=0, le=1_000_000)] = 0

    @model_validator(mode="after")
    def _shape(self) -> QueryPlan:
        if not self.dimensions and not self.measures:
            raise ValueError("a plan needs at least one dimension or measure")
        names = [m.name for m in self.measures]
        if len(names) != len(set(names)):
            raise ValueError("measure aliases must be unique")
        if set(names) & set(self.dimensions):
            raise ValueError("measure aliases must not collide with dimensions")
        if len(self.dimensions) != len(set(self.dimensions)):
            raise ValueError("dimensions must be unique")
        if self.having and not self.measures:
            raise ValueError("'having' needs measures")
        return self
