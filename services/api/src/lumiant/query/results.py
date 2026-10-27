"""Result envelope shared by every data endpoint: {data, columns, provenance, warnings, page}."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_json_value(value: Any) -> Any:
    """Decimals become strings (never floats); dates/timestamps become ISO-8601."""
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    kind: str  # dimension | measure


@dataclass(frozen=True)
class ResultWarning:
    code: str
    message: str


@dataclass
class QueryResult:
    columns: list[Column]
    rows: list[dict[str, Any]]
    provenance: dict[str, Any]
    warnings: list[ResultWarning] = field(default_factory=list)
    truncated: bool = False
    page: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None

    def payload(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "data": [{k: to_json_value(v) for k, v in row.items()} for row in self.rows],
            "columns": [c.__dict__ for c in self.columns],
            "provenance": self.provenance,
            "warnings": [w.__dict__ for w in self.warnings],
        }
        if self.page is not None:
            body["page"] = self.page
        if self.summary is not None:
            body["summary"] = {k: to_json_value(v) for k, v in self.summary.items()}
        return body
