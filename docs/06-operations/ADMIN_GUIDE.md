# Administrator Guide

## Onboarding a data source (checklist)
1. Obtain written authorization, an approved test environment and a **read-only** account (`03-security/SECURITY_PLAN.md`).
2. Write the tenant YAML: connection (`secret_ref`, never inline secrets), mapping, roles, policies, item-coding rules, `oidc`, `ai` (`02-architecture/MAPPING.md`).
3. Start the API; it refuses to start on an invalid file and says which key is wrong.
4. **Admin → Connection and schema**: the verdict must be *Mapping matches the source*. Review "unmapped columns" — never assume similarly named columns mean the same thing.
5. **Admin → Capabilities**: confirm what the mapping unlocks; missing fields are listed exactly.
6. **Admin → Reconciliation**: paste the customer's authoritative inventory-value report; every line must match within the tolerance.
7. Agree the metric and costing definitions with the customer; only then mark them approved.
8. Configure the identity provider groups under `oidc.group_roles` / `group_scopes`.
9. Decide on AI: leave `ai.external_provider_approved: false` unless the customer has approved an external provider.

## Roles and scope
Roles are configurable per tenant (`roles:` in the YAML). Scope is the set of warehouses a user can see, derived from IdP groups
(`oidc.group_scopes`) by department or explicit warehouse list. `cost:read` controls every value and price; `export:data`
controls downloads; `admin:tenant` and `audit:read` control this area.

## Audit
**Admin → Audit log** lists who asked for what and whether it was allowed. It never stores result values or filter values.
Filter by decision (denied) or action prefix (`export:`, `agent:`, `metric:`).

## Changing mappings
Edit the YAML in git (the history is the approval record), review, deploy, then re-run the schema check and reconciliation.
A mapping editor with an approval workflow is not built yet (ISSUES #15).
