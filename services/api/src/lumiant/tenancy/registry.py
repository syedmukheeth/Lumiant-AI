"""Loads and cross-validates tenant configuration files. The API refuses to start on any error."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import yaml
from pydantic import ValidationError

from lumiant.canonical.catalog import CATALOG, DatasetDef, FieldRole, FieldType
from lumiant.tenancy.models import DevUser, TenantConfig

ATTRIBUTE_PREFIX = "attr_"
# Relative to the API directory; `services/api/var/` is git-ignored (docs/07-customer/CLIENT_DATA_INTAKE.md).
PRIVATE_DATA_PREFIX = "var/private"


class TenantConfigError(Exception):
    def __init__(self, source: str, problems: list[str]) -> None:
        super().__init__(f"{source}: " + "; ".join(problems))
        self.source = source
        self.problems = problems


def cross_validate(cfg: TenantConfig, catalog: dict[str, DatasetDef] = CATALOG) -> list[str]:
    """Checks that cannot be expressed in the Pydantic schema alone."""
    problems: list[str] = []

    for ds_name, ds_map in cfg.datasets.items():
        ds = catalog.get(ds_name)
        if ds is None:
            problems.append(f"datasets.{ds_name}: not a canonical dataset")
            continue
        for field_name in ds_map.fields:
            fdef = ds.fields.get(field_name)
            if fdef is None:
                problems.append(f"datasets.{ds_name}.fields.{field_name}: not a field of {ds_name}")
            elif fdef.computed:
                problems.append(f"datasets.{ds_name}.fields.{field_name}: computed fields cannot be mapped")
        for required in ds.required_fields:
            if required not in ds_map.fields:
                problems.append(f"datasets.{ds_name}: required field '{required}' is not mapped")
        for attr in ds_map.attributes:
            if f"{ATTRIBUTE_PREFIX}{attr}" in ds.fields or attr in ds.fields:
                problems.append(f"datasets.{ds_name}.attributes.{attr}: collides with a canonical field")
        for field_name, codes in ds_map.value_maps.items():
            where = f"datasets.{ds_name}.value_maps.{field_name}"
            fdef = ds.fields.get(field_name)
            if field_name not in ds_map.fields or fdef is None:
                problems.append(f"{where}: only mapped canonical fields can have a value map")
            elif fdef.type is not FieldType.STRING:
                problems.append(f"{where}: value maps apply to text fields only")
            elif fdef.role is FieldRole.KEY or fdef.scope_key:
                problems.append(f"{where}: keys cannot be value-mapped (joins and access scope rely on them)")
            if not codes:
                problems.append(f"{where}: empty value map")

    for key in cfg.source_hints:
        ds_name, _, field_name = key.partition(".")
        if ds_name not in catalog:
            problems.append(f"source_hints.{key}: not a canonical dataset")
        elif field_name and field_name not in catalog[ds_name].fields:
            problems.append(f"source_hints.{key}: not a field of {ds_name}")

    dept_ids = [d.id for d in cfg.departments]
    if len(dept_ids) != len(set(dept_ids)):
        problems.append("departments: duplicate ids")
    wh_ids = [w.id for w in cfg.warehouses]
    if len(wh_ids) != len(set(wh_ids)):
        problems.append("warehouses: duplicate ids")
    for w in cfg.warehouses:
        if w.department not in dept_ids:
            problems.append(f"warehouses.{w.id}: unknown department '{w.department}'")

    for role, perms in cfg.roles.items():
        if not perms:
            problems.append(f"roles.{role}: no permissions")

    usernames = [u.username for u in cfg.dev_users]
    if len(usernames) != len(set(usernames)):
        problems.append("dev_users: duplicate usernames")
    for user in cfg.dev_users:
        for role in user.roles:
            if role not in cfg.roles:
                problems.append(f"dev_users.{user.username}: unknown role '{role}'")
        for dept in user.departments:
            if dept not in dept_ids:
                problems.append(f"dev_users.{user.username}: unknown department '{dept}'")
        for wh in user.warehouses:
            if wh != "*" and wh not in wh_ids:
                problems.append(f"dev_users.{user.username}: unknown warehouse '{wh}'")
        if not user.departments and not user.warehouses:
            problems.append(f"dev_users.{user.username}: no data scope (departments or warehouses)")

    if cfg.oidc is not None:
        for group, role in cfg.oidc.group_roles.items():
            if role not in cfg.roles:
                problems.append(f"oidc.group_roles.{group}: unknown role '{role}'")
        for group, scope in cfg.oidc.group_scopes.items():
            if group not in cfg.oidc.group_roles:
                problems.append(f"oidc.group_scopes.{group}: group has no role mapping")
            problems += [
                f"oidc.group_scopes.{group}: unknown department '{d}'" for d in scope.departments if d not in dept_ids
            ]
            problems += [
                f"oidc.group_scopes.{group}: unknown warehouse '{w}'"
                for w in scope.warehouses
                if w != "*" and w not in wh_ids
            ]
    if cfg.data_classification == "customer" and cfg.dev_users:
        problems.append("dev_users are not allowed for customer tenants")
    if cfg.customer_extract:
        path = (cfg.connection.path or "").replace("\\", "/")
        if not path.startswith(f"{PRIVATE_DATA_PREFIX}/"):
            problems.append(f"connection.path: customer extracts must live under {PRIVATE_DATA_PREFIX}/ (git-ignored)")
    return problems


class TenantRegistry:
    def __init__(self, tenants: dict[str, TenantConfig]) -> None:
        self._tenants = tenants
        seen: dict[str, str] = {}
        for cfg in tenants.values():
            for user in cfg.dev_users:
                if user.username in seen:
                    raise TenantConfigError(
                        cfg.id, [f"dev user '{user.username}' also defined in tenant '{seen[user.username]}'"]
                    )
                seen[user.username] = cfg.id

    @classmethod
    def load(cls, directory: Path, private_dir: Path | None = None) -> TenantRegistry:
        """Load the repository's tenant configs and, in development only, the private client-extract configs.

        Customer extracts are refused in the repository directory, and the private directory holds nothing
        else, so a client tenant cannot be committed by accident or slip in beside the demo tenants.
        """
        if not directory.is_dir():
            raise TenantConfigError(str(directory), ["tenant config directory not found"])
        tenants: dict[str, TenantConfig] = {}

        def add(path: Path, *, private: bool) -> None:
            cfg = parse_tenant_file(path)
            if cfg.customer_extract and not private:
                raise TenantConfigError(
                    path.name, ["customer_extract tenants belong in LUMIANT_PRIVATE_TENANTS_DIR, not the repository"]
                )
            if private and not cfg.customer_extract:
                raise TenantConfigError(path.name, ["the private tenant directory only holds customer_extract tenants"])
            if cfg.id in tenants:
                raise TenantConfigError(path.name, [f"duplicate tenant id '{cfg.id}'"])
            tenants[cfg.id] = cfg

        for path in sorted(directory.glob("*.yaml")):
            add(path, private=False)
        if not tenants:
            raise TenantConfigError(str(directory), ["no tenant configuration files (*.yaml)"])
        if private_dir is not None:
            if not private_dir.is_dir():
                raise TenantConfigError(str(private_dir), ["private tenant config directory not found"])
            for path in sorted(private_dir.glob("*.yaml")):
                add(path, private=True)
        return cls(tenants)

    def get(self, tenant_id: str) -> TenantConfig:
        return self._tenants[tenant_id]

    def __iter__(self) -> Iterator[TenantConfig]:
        return iter(self._tenants.values())

    def ids(self) -> list[str]:
        return list(self._tenants)

    def find_dev_user(self, username: str) -> tuple[TenantConfig, DevUser] | None:
        for cfg in self._tenants.values():
            for user in cfg.dev_users:
                if user.username == username:
                    return cfg, user
        return None


def parse_tenant_file(path: Path) -> TenantConfig:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TenantConfigError(path.name, [f"invalid YAML: {exc}"]) from exc
    try:
        cfg = TenantConfig.model_validate(raw)
    except ValidationError as exc:
        problems = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise TenantConfigError(path.name, problems) from exc
    problems = cross_validate(cfg)
    if problems:
        raise TenantConfigError(path.name, problems)
    return cfg
