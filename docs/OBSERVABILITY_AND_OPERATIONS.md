# Observability and Operations

| Capability | State | Where |
|---|---|---|
| Structured JSON logs | Verified | `core/logging.py`; one `lumiant.request` line per request (method, path, status, duration) |
| Request and correlation ids | Verified | `RequestContextMiddleware`; the id is returned in error bodies and logs; user and tenant ids in context variables |
| Health checks | Verified | `/api/health` (liveness), `/api/health/ready` (sources available / total) |
| Query timing and audit | Verified | Audit records with action, dataset, rows and milliseconds; planning runs audited as `planning:*`; capability gaps as `planning:capability_gap` |
| Scenario duration | Partial | Each planning query is timed in the audit log; there is no single "planning run duration" metric |
| Connector health | Partial | Readiness reports source availability; no per-connector history |
| API error rates, latency percentiles | Missing | No metrics backend. OpenTelemetry (OTLP exporter) is the planned path, to whatever the customer runs |
| LLM usage | Partial | Disclosure log records external calls and rows sent; no token or cost metrics (no live provider) |
| Error tracking | Missing | Logs only |

**Rules:** no secrets, tokens or record values in logs. Errors are logged with a type and code, not content. Physical names appear only in provenance.

## Runbook pointers

`06-operations/RUNBOOK.md` (start, stop, regenerate synthetic data, rotate secrets), `06-operations/DEPLOYMENT.md`, `BACKUP_AND_RECOVERY.md`.
