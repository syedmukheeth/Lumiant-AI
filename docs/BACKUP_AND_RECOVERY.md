# Backup and Recovery

_Status: **documented, not tested.** No production environment exists, so no restore drill has been performed. Nothing here is claimed as verified._

## What holds state

| Store | Contents | Criticality | Source of truth elsewhere? |
|---|---|---|---|
| App database (SQLite in dev; PostgreSQL in production) | Audit trail, chat and insight history, Alembic version | High (audit is evidence) | No |
| Tenant configuration (`config/tenants/*.yaml`) | Mappings, roles, scopes | High | Yes: git |
| Customer source systems (ERP / warehouse) | Inventory and planning data | Owned by the customer | Lumiant reads only; nothing to back up |
| Synthetic DuckDB files | Demo data | Low | Regenerated deterministically (`lumiant-synthetic generate --all`) |
| Private client extracts (`var/private`) | Local analysis copies | Per agreement | The client's original files; delete per Q-023 terms |
| Secrets | Signing keys, provider keys | High | Secret manager (never in git or backups) |

## Proposed policy (to confirm with the customer)

| Item | Proposal |
|---|---|
| Scope | App database only (configuration lives in git) |
| Frequency | Managed PostgreSQL point-in-time recovery, plus a daily logical dump |
| Retention | 35 days PITR; dumps per the audit retention policy (Q-014) |
| Encryption | At rest (provider-managed keys or customer KMS); in transit TLS |
| RPO / RTO | RPO ≤ 15 min (PITR), RTO ≤ 4 h |
| Integrity check | Monthly restore into staging; compare row counts and the latest audit ids; run `alembic current` |

## Restore procedure (outline)

1. Stop the API (or scale to 0) to avoid writes.
2. Restore PostgreSQL to the target time, or load the dump into a new instance.
3. Point `LUMIANT_APP_DB_URL` at it and run `alembic upgrade head` (no-op if current).
4. Start the API and check `/api/health/ready` and the audit explorer.
5. Record the drill in `docs/logs/TEST_RUNS.md`.

**Next step:** run the first restore drill on a staging PostgreSQL once the environment exists. The suite already passes on PostgreSQL 16 (CI `api-postgres-redis`).
