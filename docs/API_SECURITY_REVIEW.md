# API Security Review

_23 Nov 2026; complements `SECURITY_AUDIT.md` and `ENTERPRISE_SECURITY_REVIEW.md`._

| Control | State | Evidence |
|---|---|---|
| Authentication on every business route | Verified | 401 before any other check (`test_planning_endpoints_are_rate_limited_per_user` asserts 401 first) |
| CSRF on state-changing requests | Verified | `require_csrf` (`X-Requested-With`); `POST /api/planning/assess` is refused without it |
| Rate limiting | **Partial** | Per-user buckets: chat 20/min, query 120/min, export 10/min, login 10/min per IP, **planning 30/min (new, all `/api/planning/*`)**, optional shared Redis store. Inventory, reports, metrics and insights routes are still unlimited (LA-11) |
| Input validation | Verified | Pydantic models; codes pattern-restricted; quantities > 0 and bounded; enums for policies; `extra="forbid"` |
| SQL injection | Verified | No SQL from users or the LLM; plans compile to parameterised SQL; sqlglot guard; read-only connections |
| Query limits and timeouts | Verified | `max_rows` per tenant, per-query timeout; the planning loader stops at 20 pages and warns |
| Expensive calculation protection | Partial | Planning rate limit, row caps and BOM depth limit (25 levels); no per-request CPU budget or background execution yet |
| Prompt injection | Verified for the built-in path | Tool results are data; planted injection text in synthetic data; LLM path tested with fakes only |
| Sensitive errors | Verified | Errors carry a code, message and request id, never stack traces (`install_error_handlers`) |
| File uploads | N/A | No upload endpoints; SAP files import through a local CLI only |
| Dependency vulnerabilities | Verified at last CI run | `pip-audit`, `pnpm audit` in CI (Next.js 16.4.5 upgrade 20 Nov) |

## Recommended next steps

1. Apply the `query` bucket to inventory, reports, metrics and insights (LA-11), and restrict `insights?fresh=true`.
2. Move heavy planning runs behind a job queue once data volumes require it; return 202 with a job id.
3. Add secret scanning and SAST to CI (LA-22).
