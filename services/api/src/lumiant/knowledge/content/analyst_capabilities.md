# What the Analyst can answer

The Analyst answers from the organisation's connected data through Lumiant's analyses. Which questions it can answer depends on which data is mapped and on the user's role; when something is missing it says what is missing instead of guessing.

## Stock on hand and its value
Questions such as how much of an item is in stock, which warehouse holds the most, or how stock splits by item group, stage, ABC class or stock status. These need stock balances: item, warehouse, quantity and unit. Inventory value, the highest-value items, the 80/20 value concentration and a computed ABC classification also need valuation prices, and the user's role must have cost access; without it the Analyst answers in quantities only. A computed ABC needs the value cutoffs from the user, because there are no universal ones.

## Shortages, reorder levels and excess
Which items are below their reorder level, which are above their maximum stock, and which have no stock policy at all. These need a reorder policy per item and warehouse (a reorder level, and a maximum for excess) as well as stock balances. Without a reorder policy the Analyst cannot say what is short or excessive, only what is on hand.

## Movement history: idle stock, usage and turns
Which stock has had no issues for a number of days, how stock ages (grouped by days since each item last left its warehouse), how much of an item is used per month, and the issues and stock behind turns and days of cover. These need stock movement history: receipts, issues, transfers and adjustments with posting dates. The month-end value trend over the past months is rebuilt from the same movements and also needs cost access. Without movements there is no way to find idle stock, ageing, usage or turns. Turns and days of cover are not separate analyses yet; the Analyst can return the issued quantities and stock behind them.

## Lots and expiry
Which lots are expired or expire within a number of days, and which lots to issue first. These need lots or batches with receipt and expiry dates, linked to the stock on hand. Pick suggestions also need reliable receipt dates.

## Costing methods and purchase prices
Comparing costing methods for one item in one warehouse (moving weighted average, periodic average, FIFO layers, lot cost, latest price) needs stock movements with unit costs, and lots or purchase records for some methods. Comparing suppliers on price needs supplier quotations. All of these need cost access.

## Planning, customer orders and suppliers
Whether open customer orders can be delivered on time, what to buy or make and when, multi-level BOM explosions, approved alternates and the choice of supplier. Open purchase order lines, and which of them are overdue, need purchase records. The planning answers need bills of materials, open customer order lines, open purchase orders, plant planning settings such as lead times and lot sizes, and supplier item data. Customer commitment protection and supplier comparison also show prices and penalties, so they need cost access.

## Master data checks
Missing descriptions, groups, units, stages or prices; possible duplicate items; items with special storage needs; and lifecycle and obsolescence reviews. These need the item master, and each check only runs on fields that are mapped: a check whose field is not mapped is reported as not mapped, not as zero problems.

## What the Analyst cannot answer
The Analyst does not forecast future demand, prices or market conditions. It cannot give profit, revenue or margin without sales data, or answer about data the organisation has not connected; for a profit, cash or cost goal it sizes the inventory levers the data can show instead (excess, idle and expiring stock, shortages and unpriced stock) and says what is missing. It cannot change anything in the source system: Lumiant never posts orders, transfers or write-offs. It never states a figure that did not come from a query: sums, differences, ratios and shares of returned figures are computed exactly by the application, never by the model. For these questions it explains what is missing and which data would make an answer possible.
