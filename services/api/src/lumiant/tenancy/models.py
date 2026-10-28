"""Tenant configuration schema (docs/02-architecture/MAPPING.md, ADR-0006). Unknown keys are rejected."""

from __future__ import annotations

from decimal import Decimal
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
CanonicalValue = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_]{0,39}$")]
DataClassification = Literal["synthetic", "customer", "customer_extract"]
HintKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)?$", max_length=130)]


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
    # Largest difference (currency units) between a source-reported value and quantity × price that is rounding.
    value_tolerance: Decimal = Field(default=Decimal("0.01"), ge=0, le=1000)


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
    # Source code → canonical value per mapped text field (e.g. SAP material type ROH → RAW). A code that is
    # present but not listed reads as "unmapped"; a missing source value stays missing.
    value_maps: dict[CanonicalName, dict[Code, CanonicalValue]] = Field(default_factory=dict)


class CodeSegment(StrictModel):
    name: CanonicalName
    start: int = Field(ge=0, le=200)
    length: int = Field(ge=1, le=200)
    allowed: list[str] | None = None  # None = any value matching the pattern is accepted


class ItemCoding(StrictModel):
    """Customer item-code rules. Nothing about segment meaning is assumed: it is all configuration."""

    pattern: str = Field(max_length=200)
    segments: list[CodeSegment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _regex(self) -> ItemCoding:
        import re

        try:
            re.compile(self.pattern)
        except re.error as exc:
            raise ValueError(f"item_coding.pattern is not a valid regex: {exc}") from exc
        return self


class GroupScope(StrictModel):
    departments: list[Code] = Field(default_factory=list)
    warehouses: list[str] = Field(default_factory=list)  # "*" = every warehouse of the tenant


class OidcConfig(StrictModel):
    """Customer IdP trust: which tokens are accepted and how IdP groups map to roles and warehouse scope."""

    issuer: Annotated[str, StringConstraints(pattern=r"^https://[^\s]+$", max_length=300)]
    audience: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    jwks_url: Annotated[str, StringConstraints(pattern=r"^https://[^\s]+$", max_length=400)]
    groups_claim: str = "groups"
    username_claim: str = "preferred_username"
    name_claim: str = "name"
    group_roles: dict[str, CanonicalName]
    group_scopes: dict[str, GroupScope] = Field(default_factory=dict)


class AiPolicy(StrictModel):
    """Whether data may leave the deployment for an external AI provider. Off until the customer approves (Q-013)."""

    external_provider_approved: bool = False


class TenantConfig(StrictModel):
    id: Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{1,40}$")]
    display_name: str = Field(min_length=1, max_length=120)
    # customer_extract: real customer files loaded locally for analysis (ADR-0008) — never in the repository,
    # never in production, dev sign-in only behind an explicit flag.
    data_classification: DataClassification
    source_system: str = Field(min_length=1, max_length=200)
    connection: ConnectionConfig
    freshness: FreshnessConfig | None = None
    policies: Policies = Policies()
    departments: list[Department]
    warehouses: list[WarehouseAssignment]
    roles: dict[CanonicalName, list[Permission]]
    dev_users: list[DevUser] = Field(default_factory=list)
    datasets: dict[CanonicalName, DatasetMapping]
    item_coding: ItemCoding | None = None
    ai: AiPolicy = AiPolicy()
    oidc: OidcConfig | None = None
    latest_price_statuses: list[str] = Field(default_factory=lambda: ["RECEIVED"])
    # Which source extract would supply a dataset (or `dataset.field`) that is not mapped yet — shown in the
    # capability matrix, e.g. inventory_transaction: "SAP MB51 / MSEG material movements".
    source_hints: dict[HintKey, Annotated[str, StringConstraints(min_length=1, max_length=200)]] = Field(
        default_factory=dict
    )

    @property
    def synthetic(self) -> bool:
        return self.data_classification == "synthetic"

    @property
    def customer_extract(self) -> bool:
        return self.data_classification == "customer_extract"

    def warehouses_of_departments(self, departments: list[str]) -> set[str]:
        wanted = set(departments)
        return {w.id for w in self.warehouses if w.department in wanted}
