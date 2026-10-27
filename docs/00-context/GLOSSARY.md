# Glossary

## Inventory and costing terms

| Term | Meaning in this project |
|---|---|
| **Item / material / SKU** | A stock-keeping unit identified by an item code. Canonical dataset `item`. |
| **Item master** | Descriptive attributes of items (description, group, stage, UoM, storage needs…). |
| **Item code scheme** | Customer-specific rules for what positions/segments of an item code mean. Configured per tenant; never assumed. |
| **Warehouse** | A stocking site/plant/store. Canonical `warehouse`. SAP-style sources often call this a *plant* (`WERKS`). |
| **Storage location** | A sub-location inside a warehouse (bin, store room). SAP-style: `LGORT`. |
| **Lot / batch** | A quantity received together, tracked with receipt date, possibly expiry. SAP-style: `CHARG`. |
| **On-hand / stock balance** | Quantity physically held at a point in time per item/warehouse/location/lot. |
| **UoM** | Unit of measure (EA, KG, L, M…). Quantities in different UoMs are **never** summed without an approved conversion. |
| **Inventory stage** | Raw material, semi-finished, finished goods, spare part, or customer-defined. |
| **Item group** | Customer grouping such as rubber, flammable, temperature-sensitive, mechanical spares, electrical. |
| **ABC classification** | Importance class (A high value … C low). May be *assigned* by the customer or *computed* by an approved method, period and value definition. Thresholds are never hardcoded. |
| **Reorder level (ROP)** | Customer-defined quantity at/under which replenishment should be triggered. We never invent it. |
| **Min / max stock** | Customer-defined bounds. Above max = excess (if policy exists). |
| **Below reorder** | On-hand (in scope) < reorder level for an item-warehouse that *has* a policy. Items with a policy and zero stock rows count as on-hand 0. |
| **Slow-moving / dormant** | No (or low) issue movement for a configured period. Definition is configurable. |
| **Ageing** | Time since receipt of stock still on hand (needs receipt dates per lot or FIFO layers). |
| **FIFO** | First In, First Out — operationally: issue the oldest eligible stock first. For costing: cost layers consumed oldest first. |
| **LIFO** | Last In, First Out — supported only as a configured *operational* issue rule; never auto-applied to accounting valuation. |
| **Moving weighted average (MWA)** | Average unit cost recomputed at each receipt: (old qty × old avg + receipt qty × receipt cost) / new qty. |
| **Periodic weighted average** | Average cost over a period: Σ(cost of opening + receipts) / Σ(qty of opening + receipts) for that period. |
| **Lot cost** | Unit cost of a specific lot. |
| **Latest price** | Customer-defined: e.g. latest *valid purchase price* or latest *approved receipt cost*. Always stated explicitly; never confused with average valuation. |
| **Valuation price** | The price used to value on-hand stock as provided by the source system (e.g. ERP moving average). |
| **Inventory value** | On-hand quantity × valuation price, aggregated **per currency**. |
| **Carrying cost** | Cost of holding inventory (capital, storage, risk). Only computed if the customer supplies the rate/definition. |

## SAP-style field names used in synthetic tenant `demo-alpha` (illustrative only)

| Name | Typical meaning | Canonical field |
|---|---|---|
| MATNR | Material number | `item_code` / `item_id` |
| MAKTX | Material description | `description` |
| MATKL | Material group | `item_group` |
| MTART | Material type | `inventory_stage` |
| WERKS | Plant | `warehouse_id` |
| LGORT | Storage location | `location_id` |
| CHARG | Batch | `lot_id` |
| LABST | Unrestricted stock quantity | `quantity` |
| MEINS | Base unit of measure | `uom` |
| VERPR | Moving average price | `valuation_price` |
| WAERS | Currency | `currency` |

These names are **not** a claim about any real customer's SAP system (see F-004).

## Project terms

| Term | Meaning |
|---|---|
| **Tenant** | One customer configuration (connection, mapping, roles, policies). Tenant identity comes only from the authenticated token. |
| **Canonical model** | Lumiant's internal, customer-independent inventory datasets and fields (`02-architecture/DATA_MODEL.md`). |
| **Mapping** | Per-tenant config translating canonical datasets/fields to physical tables/columns (`02-architecture/MAPPING.md`). |
| **QueryPlan** | Structured, validated description of a query (dataset, fields, measures, filters, grouping, sort, limit). The only way data is queried. |
| **Analysis** | A named, versioned, deterministic, tested computation (e.g. below-reorder). |
| **Metric catalog** | Named, versioned metric definitions (QueryPlan template + rule text + status `draft`/`customer-approved`). |
| **Provenance** | Machine-generated record of where a result came from: source objects/columns, filters (user + injected), as-of, rule, row count, truncation. Never hand-written. |
| **Scope injection** | Validator adds mandatory filters (e.g. allowed warehouses) after any user/LLM input, so scope cannot be widened. |
| **Principal** | The authenticated user context: user id, tenant, roles, permissions, warehouse scope. |
| **Grounding guard** (M3) | Check that every number in AI-written prose appears in tool results. |
| **Synthetic flag** | `synthetic=true` in API responses when data comes from generated demo data; drives the UI badge. |
| **AI-off mode** | Product runs without any LLM (dashboard, menu, reports still work). |
