# Deployment

Status: **Not started (M6).** Nothing has been deployed. Do not deploy to any customer environment without written approval.

## What is known
- Public hosting is **not** assumed (brief §4). The target is likely customer-controlled or a private cloud (A-006, Q-012).
- Deployables: `apps/web` (Next.js server) and `services/api` (FastAPI/uvicorn). Both containerizable.
- State: app metadata DB (PostgreSQL in production), tenant config files, and secrets (secret manager or env).
- Network: web → api (internal), api → customer warehouse (read-only), optional api → approved LLM endpoint, users → web via the customer's TLS ingress.

## Infrastructure requirements (draft)

| Need | Detail |
|---|---|
| Compute | 2 containers; api sized to query concurrency (start 2 vCPU / 2 GB) |
| Database | PostgreSQL 15+ for app metadata, encrypted at rest, backed up |
| Secrets | Secret manager (Azure Key Vault / AWS Secrets Manager / HashiCorp Vault) or orchestrator secrets |
| TLS | Terminated at ingress; HSTS |
| Identity | OIDC app registration in the customer IdP (Q-010) |
| Egress | To the warehouse; to the LLM endpoint only if approved (Q-013) |
| Logging | JSON stdout → customer log platform; audit stays in the app DB |

## To be written in M6
Environment variable reference · container build · migrations (`alembic upgrade head`) · health checks (`/api/health`, `/api/health/ready`) · monitoring · backup/restore · rollback · production-readiness checklist · admin and user guides.
