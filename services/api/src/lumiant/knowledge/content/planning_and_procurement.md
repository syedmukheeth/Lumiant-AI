# Planning, procurement and customer commitments

The planning module is deterministic: it calculates from the customer's bills of materials, stock, open orders, supplier data and lead times. Every output is a recommendation; Lumiant never posts orders or changes data in the source system.

## Bill of materials (BOM) explosion
A BOM explosion multiplies the quantity of a finished or semi-finished item through every level of its bill of materials to show the components and quantities it needs. Component quantities stay in their own units.

## Material requirements planning (MRP)
MRP is time-phased: for each item it compares demand (customer order lines and dependent demand from BOMs) with supply (stock on hand and open purchase or production orders) over time, and shows when and by how much the item falls short. Planned receipts respect supplier lead times.

## Order fulfilment and at-risk orders
A customer order line is at risk when the components or stock it needs will not be available by its due date. Fulfilment views show which lines can be served from stock, which are short and why.

## Customer commitment protection
Commitment protection looks at a customer order at risk and lists options to keep the promise: use stock in another warehouse (transfer), an approved alternate item, a faster supplier, or a partial delivery. Each option shows its timing and cost impact so a planner can decide.

## Supplier comparison
Suppliers for an item are compared on price, lead time and recorded delivery performance. Delivery comes first: a cheaper supplier that would deliver late is not recommended for an at-risk order.

## Lead time
Lead time is the time from placing a purchase order to receiving the goods. Lumiant uses the supplier and item lead time recorded in the source data and does not invent one when it is missing.

## Alternate items
An alternate item is an approved substitute for another item. Only alternates recorded in the source data are suggested.

## Duplicate items
Possible duplicate items are different item codes that look like the same physical part, for example the same manufacturer part number or a near-identical description. They are candidates for a person to review, not automatic merges.

## Lifecycle and obsolescence
Lifecycle status (active, superseded, discontinued) comes from the item master. Obsolescence is never predicted from inactivity alone: critical spares can sit unused for years on purpose.
