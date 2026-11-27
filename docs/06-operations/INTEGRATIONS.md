# Integrations: API keys, public API and MCP

How a customer's own systems and AI assistants use Lumiant (PRODUCT_V3_PLAN §4, V3). Every integration acts through an
**API key**, so it has exactly the rights and warehouse scope given to it, and every call is audited.

## API keys

Admin › Integrations (`admin:tenant`): name the key, tick what it may do, create. The key (`lmk_<id>_<secret>`) is
shown **once**; only its SHA-256 hash is stored. Revoke it there at any time; a revoked key gets 401 at once.

Rules enforced by the API (`apikeys/store.py`):
- Grantable rights: dashboards, inventory, costs and values, queries, Analyst, exports. Never administration or the
  audit log.
- A key never exceeds its creator: rights are a subset of the creator's, warehouses inside the creator's scope.
- Requests with a key need no CSRF header (there is no browser session to abuse) and are audited as `apikey:<id>`.

## Public API

Every read endpoint in `02-architecture/API_CONTRACTS.md` accepts `Authorization: Bearer lmk_...`:

```bash
curl -H "Authorization: Bearer $LUMIANT_KEY" https://lumiant.example.com/api/metrics/inventory_value_by_warehouse
curl -H "Authorization: Bearer $LUMIANT_KEY" -H "Content-Type: application/json" \
     -d '{"dataset":"stock_balance","dimensions":["warehouse_id"],"measures":[{"field":"quantity","agg":"sum","alias":"qty"}]}' \
     https://lumiant.example.com/api/query
```

Figures are strings with their currency and unit, and each response carries provenance (source objects, filters,
injected warehouse scope, data timestamp). Rate limits apply per key.

## MCP server (AI assistants)

`POST /mcp` speaks the Model Context Protocol (Streamable HTTP, JSON responses; protocol versions 2025-06-18,
2025-03-26, 2024-11-05). Tools: every analysis the key may run (the same typed tools as the Analyst) plus
`ask_lumiant` for a plain-language question. All tools are read-only. The assistant chooses a tool and typed
arguments; Lumiant runs validated queries and returns exact figures with provenance (ADR-0002: no SQL from the model,
no model-made numbers).

Client configuration (Claude Desktop / Claude Code style; other clients take the same URL and header):

```json
{
  "mcpServers": {
    "lumiant": {
      "type": "http",
      "url": "https://lumiant.example.com/mcp",
      "headers": { "Authorization": "Bearer lmk_..." }
    }
  }
}
```

What the customer should know before connecting an external assistant: the tool **results** (figures, item codes,
warehouse names within the key's scope) go to that assistant's provider. Give such keys the narrowest rights and
warehouses, and follow the customer's AI provider approval (OPEN_QUESTIONS Q-013).

## Alert rules (signed webhooks)

Admin › Integrations › Alert rules: name, https address, minimum severity. The signing secret (`whsec_...`) is shown
once and stored encrypted (needs `LUMIANT_SECRET_KEY`). "Send now" (or `POST /api/admin/alerts/{id}/send`) computes the
findings with the sender's scope and posts JSON `{rule, tenant_id, timestamp, data_as_of, complete, warnings, findings[]}`
with headers `X-Lumiant-Signature: sha256=<hex>` and `X-Lumiant-Timestamp`. Verify on the receiver:

```python
import hashlib, hmac
expected = "sha256=" + hmac.new(SECRET.encode(), request_body_bytes, hashlib.sha256).hexdigest()
assert hmac.compare_digest(expected, request.headers["X-Lumiant-Signature"])
```

Reject deliveries whose timestamp is more than a few minutes old. In production targets must be https and may not
resolve to private, loopback, link-local or reserved addresses.

**Scheduled rules** (every hour, day or week) are sent by `uv run lumiant-alerts send-due`, run from cron or a
Kubernetes CronJob every 15 minutes. A scheduled run uses the creator's rights and warehouse scope as they were when
the rule was created (snapshot), never more. Unscheduled rules are only sent with "Send now".

## Not built yet

Embeddable widgets with signed tokens, Teams/Slack apps and the Excel add-in
(PRODUCT_V3_PLAN §4) follow on this key model.
