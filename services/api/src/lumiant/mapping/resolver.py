"""Canonical → physical resolution for one tenant (docs/02-architecture/MAPPING.md).

A canonical field is available for a tenant only if it is explicitly mapped (or, for computed fields,
all of its operands are mapped). Nothing is ever guessed from column names.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlalchemy as sa
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from lumiant.canonical.catalog import CATALOG, DatasetDef, FieldDef, FieldRole, FieldType
from lumiant.tenancy.models import TenantConfig
from lumiant.tenancy.registry import ATTRIBUTE_PREFIX

SA_TYPES: dict[FieldType, sa.types.TypeEngine[Any]] = {
    FieldType.STRING: sa.String(),
    FieldType.INTEGER: sa.Integer(),
    FieldType.DECIMAL: sa.Numeric(18, 4, asdecimal=True),
    FieldType.DATE: sa.Date(),
    FieldType.DATETIME: sa.DateTime(),
    FieldType.BOOLEAN: sa.Boolean(),
}


@dataclass(frozen=True)
class SourceObject:
    schema: str | None
    name: str

    @classmethod
    def parse(cls, ref: str) -> SourceObject:
        schema, _, name = ref.rpartition(".")
        return cls(schema or None, name)

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name


class TenantMapping:
    def __init__(self, tenant: TenantConfig, catalog: dict[str, DatasetDef] = CATALOG) -> None:
        self.tenant = tenant
        self._catalog = catalog
        self._metadata = sa.MetaData()
        self._tables: dict[str, sa.Table] = {}
        self._columns: dict[str, dict[str, str]] = {}
        self._fields: dict[str, dict[str, FieldDef]] = {}
        self._value_maps: dict[str, dict[str, dict[str, str]]] = {}
        for ds_name, ds_map in tenant.datasets.items():
            ds = catalog[ds_name]
            columns: dict[str, str] = dict(ds_map.fields)
            available: dict[str, FieldDef] = {}
            for fdef in ds.fields.values():
                if fdef.product_of is not None:
                    if all(op in columns for op in fdef.product_of):
                        available[fdef.name] = fdef
                elif fdef.name in columns:
                    available[fdef.name] = fdef
            for attr_name, attr in ds_map.attributes.items():
                name = f"{ATTRIBUTE_PREFIX}{attr_name}"
                columns[name] = attr.column
                available[name] = FieldDef(
                    name,
                    attr.type,
                    FieldRole.ATTRIBUTE,
                    attr.description or f"Customer attribute {attr_name}",
                )
            self._columns[ds_name] = columns
            self._fields[ds_name] = available
            self._value_maps[ds_name] = {f: dict(codes) for f, codes in ds_map.value_maps.items()}
            src = SourceObject.parse(ds_map.source)
            physical: dict[str, FieldType] = {}
            for fname, col in columns.items():
                physical.setdefault(col, available[fname].type)
            self._tables[ds_name] = sa.Table(
                src.name,
                self._metadata,
                *(sa.Column(col, SA_TYPES[ftype]) for col, ftype in physical.items()),
                schema=src.schema,
            )

    # --- lookups -------------------------------------------------------------------------------
    def is_mapped(self, dataset: str) -> bool:
        return dataset in self._tables

    def fields(self, dataset: str) -> dict[str, FieldDef]:
        return self._fields.get(dataset, {})

    def field(self, dataset: str, name: str) -> FieldDef | None:
        return self._fields.get(dataset, {}).get(name)

    def has_ref(self, dataset: str, ref: str) -> bool:
        """Whether a plan reference such as `quantity` or `item.item_group` resolves for this tenant."""
        join_name, _, name = ref.rpartition(".")
        if not join_name:
            return self.field(dataset, name) is not None
        ds = self._catalog.get(dataset)
        join = ds.joins.get(join_name) if ds else None
        if join is None or not self.is_mapped(join.dataset):
            return False
        if any(
            self.field(dataset, local) is None or self.field(join.dataset, remote) is None for local, remote in join.on
        ):
            return False
        return self.field(join.dataset, name) is not None

    def table(self, dataset: str) -> sa.Table:
        return self._tables[dataset]

    def source_object(self, dataset: str) -> str:
        return self.tenant.datasets[dataset].source

    def physical_column(self, dataset: str, name: str) -> str:
        return self._columns[dataset][name]

    def physical_tables(self) -> set[str]:
        """Lower-cased table names (qualified and bare) for the SQL guard allowlist."""
        names: set[str] = set()
        for ds_map in self.tenant.datasets.values():
            src = SourceObject.parse(ds_map.source)
            names.add(src.qualified.lower())
            names.add(src.name.lower())
        return names

    def value_maps(self) -> dict[str, dict[str, dict[str, str]]]:
        """dataset → field → {source code: canonical value}, for the fields that have a value map."""
        return {ds: maps for ds, maps in self._value_maps.items() if maps}

    # --- expressions ---------------------------------------------------------------------------
    def column_expr(self, dataset: str, name: str, source: FromClause) -> ColumnElement[object]:
        fdef = self._fields[dataset][name]
        if fdef.product_of is not None:
            left, right = (source.c[self._columns[dataset][op]] for op in fdef.product_of)
            return left * right
        col: ColumnElement[object] = source.c[self._columns[dataset][name]]
        codes = self._value_maps.get(dataset, {}).get(name)
        if codes:
            # Constants come from validated tenant config and render inline, so the same CASE text appears in
            # SELECT, GROUP BY and ORDER BY (distinct bind parameters would make them differ).
            return sa.case(
                (col.is_(None), sa.null()),
                *((col == _const(code), _const(value)) for code, value in sorted(codes.items())),
                else_=_const(UNMAPPED),
            )
        return col

    def physical_ref(self, dataset: str, name: str) -> str:
        fdef = self._fields[dataset][name]
        src = self.source_object(dataset)
        if fdef.product_of is not None:
            return " * ".join(f"{src}.{self._columns[dataset][op]}" for op in fdef.product_of)
        ref = f"{src}.{self._columns[dataset][name]}"
        if self._value_maps.get(dataset, {}).get(name):
            return f"value_map({ref})"
        return ref


UNMAPPED = "unmapped"


def _const(value: str) -> ColumnElement[str]:
    return sa.bindparam(None, value, type_=sa.String(), literal_execute=True)
