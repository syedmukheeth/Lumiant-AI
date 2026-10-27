# User Guide

What you can do depends on your role; options you cannot use are not shown. Everything you see comes from your organisation's
data warehouse, limited to the warehouses you are allowed to view. The orange SYNTHETIC badge means the data is generated
demonstration data.

| Page | Use it to |
|---|---|
| **Overview** | See inventory value (per currency, never added together), items in stock, items below reorder level, and value by warehouse, group, ABC class and stage. |
| **Explore** | Pick a task from a menu (analyze stock, compare warehouses, find slow-moving items, review risks, check data quality, make a report). |
| **Inventory** | Search and filter every stock line; sort and page through them. |
| **Risks** | Excess stock, dormant stock, expiring lots, master-data gaps. |
| **Costs** | Compare costing methods for one item and warehouse; compare computed and assigned ABC classes. These are *draft* definitions until your organisation approves them. |
| **Assistant** | Ask in your own words. It chooses a checked analysis, shows a table or chart and tells you where the numbers came from. It says so when it cannot answer; it never guesses. |
| **Reports** | Preview, download (CSV or Excel) or print a report. Each carries the filters, data time, access scope and any notices. |

## Reading a number
Click **Source** next to any figure: it lists the source tables and columns, your filters, the access scope applied by your
permissions, the rule used, the data time and the number of rows.

## Good to know
- "Data as of" is when the warehouse was last refreshed; it turns orange when stale.
- A dash (—) means missing in the source, not zero.
- Amounts in different currencies or units are shown separately.
- Exports are recorded in the audit log.
