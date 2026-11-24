# Enterprise Security Review

_23 Nov 2026. This review adds the planning features to the baseline in `SECURITY_AUDIT.md` (31 Oct 2026). It is an engineering review, not a penetration test or certification._

## 1. New surface (this phase) and its controls

| Surface | Control | Evidence |
|---|---|---|
| `/api/planning/*` | `inventory:read` required; suppliers also need `cost:read`; `assess` is POST with CSRF | `api/planning.py`; `test_planning_api_scope_and_permissions` |
| Planning data access | Only through `QueryService.run_plan`: tenant mapping, injected warehouse scope (orders, stock, POs, plant data), cost-field check, row limits, audit | `planning/loader.py`; `test_planner_sees_only_their_warehouse` |
| Supplier quotations | Cost-sensitive fields (`supplier_item.price`, `freight_per_unit`); no supplier-facing access exists | catalog sensitivity; `test_supplier_prices_need_cost_access` |
| Assistant planning tools | Tool permissions are filtered per role; the matcher refuses supplier questions without cost access; answers are grounded | `test_assistant_supplier_question_without_cost_access_is_refused`; grounding passes in routing tests |
| Navigation | Sections are computed server-side from role and tenant data | `test_planning_sections_follow_role_and_tenant_data` |
| Inputs | Pydantic validation (codes pattern-restricted, quantities > 0 and bounded, policy enum) | `api/planning.py` |
| Writes | None. All planning output is recommendation-only | code review |
| Client SAP files | Imported locally to git-ignored `var/private`; `customer_extract` tenants refuse external AI; never committed | `.gitignore`; `git check-ignore` (20 Nov) |
| Secrets | No `.env` in the repository; the shareable `.env.dev-share` has no secrets and is git-ignored | `git check-ignore` (22 Nov) |

## 2. Open findings carried over (status not re-tested this session)

| ID | Priority | Finding | Needed before production |
|---|---|---|---|
| LA-01 | P0 | OIDC browser path (backend-for-frontend, PKCE, server sessions) | Yes |
| LA-06 | P1 | Development defaults and username-only dev login | Yes: production-safe defaults |
| LA-07 / LA-10 | P1 | AI boundary and grounding strength | Yes, before enabling an external LLM |
| LA-11 | P1 | Rate limiting covers few routes (planning endpoints are not rate-limited either) | Yes |
| LA-13 | P1 | Coarse authorization (item and supplier master tenant-wide; one sensitivity class) | Yes for multi-department customers |
| LA-21 | P1 | Public repository without a licence | Owner decision |
| LA-28 | P1 | Client data consent terms (Q-023) | Yes |
| LA-12, LA-15, LA-20, LA-22, LA-23, LA-30 | P2 | Session revocation, pool timeout code, tamper-evident audit, supply-chain scanning, container hardening, OIDC checks | Hardening plan |

## 3. Planning-specific risks and mitigations

- **Large planning reads** page through `max_rows` up to 20 pages, then warn (`data_truncated`). There is no denial-of-service ceiling beyond query timeouts. Mitigation: add planning endpoints to the rate limiter (part of LA-11) and aggregate in SQL.
- **Supplier data exposure across departments:** supplier master is tenant-wide (LA-13). Quotations are cost-gated.
- **Prompt injection through master data** (descriptions, notes): treated as untrusted data. The planning tools never execute text, and synthetic data still plants an injection string to test resistance.
- **Recommendation misuse:** results are labelled recommendation-only in the API (`recommendation_only: true`), the UI and the assistant.

## 4. Saudi deployment considerations (need legal review)

Data residency (in-Kingdom hosting or customer-hosted), PDPL obligations for any personal data (user identities, supplier contacts), data-processing agreements with any AI provider, NCA controls where the customer requires them, incident management and audit retention. **No compliance or certification is claimed.**
