"""Connector contract (docs/02-architecture/CONNECTORS.md). There is deliberately no execute(sql_string)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import sqlalchemy as sa
from sqlalchemy.engine import Dialect


@dataclass(frozen=True)
class RawResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    duration_ms: float


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type: str
    nullable: bool


@dataclass(frozen=True)
class ObjectInfo:
    schema: str | None
    name: str
    kind: str  # "table" | "view"


class ConnectorError(Exception):
    """Failure talking to a source. `code` is safe to show; the cause stays in server logs."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class Connector(Protocol):
    dialect_name: str

    @property
    def dialect(self) -> Dialect: ...

    def health(self) -> bool: ...

    def has_table(self, schema: str | None, name: str) -> bool: ...

    def list_objects(self) -> list[ObjectInfo]: ...

    def describe(self, schema: str | None, name: str) -> list[ColumnInfo]: ...

    def execute(self, stmt: sa.Select[Any], *, fetch_limit: int, timeout_s: float) -> RawResult: ...

    def dispose(self) -> None: ...
