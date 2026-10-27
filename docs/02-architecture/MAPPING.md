# Tenant Mapping

Status: **Designed**; M1 implements loading/validation in `services/api/src/lumiant/tenancy/` and resolution in `mapping/`.

## File

`services/api/config/tenants/<tenant-id>.yaml`. Validated by Pydantic at startup — the API refuses to start with an invalid tenant file and prints which key is wrong.

## Shape (abridged)

```yaml
id: demo-alpha
display_name: "Demo Alpha Manufacturing (synthetic)"
data_classification: synthetic          # synthetic | customer
connection:
  type: duckdb
  path: data/synthetic/demo_alpha.duckdb # relative to services/api; customer DBs use secret_ref
  # secret_ref: env:ALPHA_DW_URL         # never inline credentials
freshness:
  object: _extract_metadata
  column: extracted_at
policies:
  max_rows: 1000
  query_timeout_s: 15
  stale_after_hours: 36
departments:
  - {id: NORTH, name: "North Plant Operations"}
warehouses:                               # warehouse → department, used for scope derivation
  - {id: "1100", department: NORTH}
roles:
  super_admin: [dashboard:read, inventory:read, cost:read, query:run, query:view_sql, audit:read, admin:tenant]
dev_users:                                # ignored unless AUTH_MODE=dev and APP_ENV != production
  - {username: alpha.admin, display_name: "Alpha Admin", roles: [super_admin], warehouses: ["*"]}
datasets:
  stock_balance:
    source: ZV_STOCK
    fields:
      item_id: MATNR
      warehouse_id: WERKS
      location_id: LGORT
      lot_id: CHARG
      quantity: LABST
      uom: MEINS
      valuation_price: VERPR
      currency: WAERS
  item:
    source: ZV_MATERIAL
    fields: {item_id: MATNR, item_code: MATNR, description: MAKTX, item_group: MATKL, ...}
    attributes:                           # extension attributes (customer-specific)
      colour: {column: ZZCOLOR, type: string}
```

## Rules

- A canonical field missing from the mapping is **not available** for that tenant — the validator rejects it and the capability matrix (M3) explains it. We never guess a column.
- Two columns with similar names are never assumed equivalent (brief §5.3); mapping is explicit.
- Computed canonical fields (e.g. `stock_value`) are defined in the canonical catalog, not per tenant, so their meaning is identical everywhere.
- `item_code` and `item_id` may map to the same column.
- Extension attributes are addressed as `attr_<name>` in plans (e.g. `item.attr_colour`).
- Mapping changes are code-reviewed config changes (git history = mapping history) until the mapping studio (M5) adds approval workflow.

## Validation performed at startup

1. YAML schema valid; unknown keys rejected.
2. Every mapped dataset/field exists in the canonical catalog.
3. Required key fields mapped for each mapped dataset (e.g. `stock_balance` needs item_id, warehouse_id, quantity, uom).
4. Roles reference known permissions; dev users reference known roles and warehouses.
5. Connection type is a registered connector; customer connections use `secret_ref`, never inline secrets.

Physical existence of mapped columns is checked by `/api/health/ready` (and in tests) using `connector.describe()`.
