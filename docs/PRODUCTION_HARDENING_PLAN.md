# Production Hardening Plan

Ordered by risk. Each step lists what was done this session (23 Nov 2026) and what remains, with the evidence that will close it.

| # | Item | Finding | Done (23 Nov) | Remaining | Closing evidence |
|---|---|---|---|---|---|
| 1 | Production sign-in | LA-01 (P0) | Web no longer forces the dev sign-in page in OIDC mode (`proxy.ts` `needsDevLogin`, unit test). The API's OIDC validation already existed | Gateway in front of web and API; OIDC sign-out; optional built-in code + PKCE flow | E2E against a Keycloak container in CI, then the customer's IdP in staging |
| 2 | Safe defaults | LA-06 (P1) | Production already refuses dev auth (startup validation) | Default `app_env` stays `development` for local work. Production images set `production` explicitly; add a CI check that the production image refuses to start without OIDC settings | Container test |
| 3 | Rate limits everywhere | LA-11 (P1) | Planning routes limited (30/min per user), tested | Inventory, reports, metrics, insights (`fresh=true`) | Tests like `test_planning_endpoints_are_rate_limited_per_user` per route group |
| 4 | Fine-grained policies | LA-13 (P1) | Planning sections and endpoints gated by permission and tenant data; supplier quotes cost-gated | `procurement` sensitivity class; master-data scope; hide physical names | Validator tests |
| 5 | AI boundary | LA-07 / LA-10 | Unchanged (built-in matcher only; no external calls) | Before any external LLM: intent-only default, stronger grounding | Tests plus live check with tenant approval |
| 6 | Audit integrity and retention | LA-20 | Planning runs and capability gaps audited | Hash chain or WORM export; retention (Q-014) | Tamper test |
| 7 | Observability | — | Request ids, structured logs, audit timings | OpenTelemetry metrics and traces; error tracking | Dashboard in staging |
| 8 | Backups and DR | — | Policy and procedure written (`BACKUP_AND_RECOVERY.md`) | First restore drill | Drill record in `TEST_RUNS.md` |
| 9 | Performance | ISSUES #6 | Engine benchmark at enterprise volumes (`PERFORMANCE_AND_LOAD_TESTING.md`) | Aggregated SQL read path for planning; HTTP load test with concurrent users | k6 or Locust report on staging |
| 10 | Supply chain | LA-22 | Next.js upgraded for advisories (20 Nov); CI audits | Secret scanning, SAST, image digests, SBOM | CI jobs green |
| 11 | Repository governance | LA-21, LA-28 | — | Private repository and licence; client data consent terms | Owner decision, signed terms |
