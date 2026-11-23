# Sample Data and Licence Audit

The full audit is in **`SCENARIO_DATASET_AND_LICENSE_AUDIT.md`** (22 Nov 2026), with the earlier terminology-source audit in `AI_DOMAIN_REINFORCEMENT_RESEARCH.md` (19 Nov 2026). Summary:

| Source | Licence | Commercial use | Training | Planning coverage (suppliers / BOM / procurement / lead times) | Decision |
|---|---|---|---|---|---|
| pantalytics/odoo-demo-data | MIT | Yes | Yes | Odoo demo records | Later import test (needs an Odoo connector) |
| odoo/odoo 18 (mrp, stock, purchase) | LGPL-3 | Yes | Facts and structure | BOM (incl. phantom kits), supplier info (price, min qty, delay) | Structural reference; nothing copied |
| SAP-samples/datasphere-content | Apache-2.0 (per file) | Yes | Per file | Analytics models; no planning data | Reference |
| SAP-samples/liteinventorymanagement | Apache-2.0 | Yes | Code | Goods receipt and issue only | Reference |
| SAP-samples/hana-cloud-learning | Apache-2.0 | Yes | Per file | None relevant | Not used |
| SAP/SALT | CC BY-NC-SA 4.0 | **No** | **No** | Sales orders | **Excluded** |
| aalomair/erpnext-synthetic-dataset | MIT | Yes | Yes | Suppliers, POs, receipts, lead times, price variance; **no BOM** | Reference; needs a live ERPNext v16 to generate; repository 3 days old at review |
| Oracle Fusion SCM docs | Documentation terms | Facts only | No | API and table definitions, no dataset | Mapping facts only |

**Synthetic data used instead:** `demo-delta` (manufacturing, hand-authored, deterministic) and 66 scenario fixtures (85 checks). All are marked synthetic and use fictional names. No dataset was purchased, no paid API was called, and no model was trained.

**Distinguishing record origins:** public sample records (none imported), documentation facts (field names only), synthetic records (`_dataset_info.synthetic = true`), and the client's private extract (local only, `customer_extract`, never committed).
