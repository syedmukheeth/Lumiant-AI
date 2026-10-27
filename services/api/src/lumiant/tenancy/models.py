"""Tenant configuration schema (docs/02-architecture/MAPPING.md, ADR-0006). Unknown keys are rejected."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from lumiant.auth.permissions import Permission
from lumiant.canonical.catalog import FieldType

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_$]*$", max_length=128)]
SourceObject = Annotated[
    str, StringConstraints(pattern=r"^([A-Za-z_][A-Za-z0-9_$]*\.)?[A-Za-z_][A-Za-z0-9_$]*$", max_length=200)
]
CanonicalName = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", max_length=64)]
Code = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConnectionConfig(StrictModel):
    type: Literal["duckdb"]
    # Relative to the API base directory. Customer databases use secret_ref instead of inline values.
    path: str | None = None
    secret_ref: str | None = Field(default=None, pattern=r"^env:[A-Z][A-Z0-9_]*$")

    @model_validator(mode="after")
    def _check(self) -> ConnectionConfig:
        if self.type == "duckdb":
            if not self.path:
                raise ValueError("duckdb connections need a 'path'")
            p = PurePosixPath(self.path.replace("\\", "/"))
            if p.is_absolute() or ".." in p.parts or ":" in self.path:
                raise ValueError("connection path must be relative to the API directory and stay inside it")
        return self


class FreshnessConfig(StrictModel):
    object: SourceObject
    column: Identifier


class Policies(StrictModel):
    max_rows: int = Field(default=1000, ge=1, le=10_000)
    default_rows: int = Field(default=100, ge=1, le=1000)
    query_timeout_s: float = Field(default=15.0, gt=0, le=120)
    stale_after_hours: int = Field(default=36, ge=1, le=24 * 90)


class Department(StrictModel):
    id: Code
    name: str = Field(min_length=1, max_length=120)


class WarehouseAssignment(StrictModel):
    id: Code
    department: Code


class DevUser(StrictModel):
    username: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]{2,63}$")]
    display_name: str = Field(min_length=1, max_length=120)
    roles: list[CanonicalName] = Field(min_length=1)
    departments: list[Code] = Field(default_factory=list)
    warehouses: list[str] = Field(default_factory=list)


class AttributeMapping(StrictModel):
    column: Identifier
    type: FieldType
    description: str = ""


class DatasetMapping(StrictModel):
    source: SourceObject
    fields: dict[CanonicalName, Identifier]
    attributes: dict[CanonicalName, AttributeMapping] = Field(default_factory=dict)


class TenantConfig(StrictModel):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,40}$")]
    display_name: str = Field(min_length=1, max_length=120)
    data_classification: Literal["synthetic", "customer"]
    source_system: str = Field(min_length=1, max_length=200)
    connection: ConnectionConfig
    freshness: FreshnessConfig | None = None
    policies: Policies = Policies()
    departments: list[Department]
    warehouses: list[WarehouseAssignment]
    roles: dict[CanonicalName, list[Permission]]
    dev_users: list[DevUser] = Field(default_factory=list)
    datasets: dict[CanonicalName, DatasetMapping]

    @property
    def synthetic(self) -> bool:
        return self.data_classification == "synthetic"

    def warehouses_of_departments(self, departments: list[str]) -> set[str]:
        wanted = set(departments)
        return {w.id for w in self.warehouses if w.department in wanted}
