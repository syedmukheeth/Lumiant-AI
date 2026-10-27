# Operations Runbook (draft)

Written for the target deployment; none of it has been rehearsed. Rehearse before go-live.

## Health
| Check | Meaning |
|---|---|
| `GET /api/health` | process is up |
| `GET /api/health/ready` | `{status, sources_available, sources_total}`; 503 when a warehouse is unreachable (no details exposed) |

## Common problems
| Symptom | Likely cause | Action |
|---|---|---|
| Users see "The data source is currently unavailable" (503 `source_unavailable`) | warehouse down, credential or network change | check `/api/health/ready`; verify the read-only account; look for `connect_failed` in logs |
| "The query took too long" (504 `query_timeout`) | broad query on a large table | narrow filters; review the tenant `query_timeout_s`; ask the customer for an indexed view |
| 401 everywhere after a deploy | IdP keys rotated or gateway not forwarding the token | check `oidc_token_rejected` / `oidc_verification_failed` log lines (no token content is logged) |
| 403 `no_access` for a valid user | user's IdP group has no role mapping | add the group under `oidc.group_roles` in the tenant YAML |
| 429 `rate_limited` | limits too low or a client loop | check audit log for the user; adjust `LUMIANT_RATE_LIMIT_*` |
| 503 `audit_unavailable` | app database unreachable (writes fail closed) | restore the database; no data is served without an audit record |
| Mapping/data mismatch after a customer schema change | drift | Admin → Connection and schema; update the mapping |

## Backup and recovery
- App database (audit, future saved items): daily backups plus before every release; test a restore quarterly.
- Tenant YAML and mappings live in git; the repository is the source of truth.
- The warehouse is the customer's system; the platform holds no copy of it.

## Incident handling
1. Contain: disable the affected route at the gateway or set `LUMIANT_AGENT_PROVIDER=rules`.
2. Investigate with request ids (`X-Request-ID`) across logs and the audit trail.
3. Never export logs containing secrets; none are written by design.
4. Record a post-mortem in `docs/logs/`.

## Rotating things
- IdP signing keys: automatic through JWKS (cached up to one hour).
- Warehouse credentials: update the secret, restart the api.
- AI provider key: update the secret; disable by setting the provider to `rules`.
