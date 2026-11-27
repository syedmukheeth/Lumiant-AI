# Costing methods

Lumiant compares costing methods for one item in one warehouse. These are draft definitions pending customer approval; the customer's accounting policy decides which one is official.

## Moving weighted average (MWA)
On each receipt the average becomes (quantity before × average before + quantity received × receipt cost) ÷ (quantity before + quantity received). Issues do not change the average.

## Periodic weighted average
For a period: (opening value + value of all receipts in the period) ÷ (opening quantity + quantity of all receipts in the period).

## FIFO cost layers
First in, first out: every receipt adds a cost layer and issues consume the oldest layers first. The remaining layers give the value of stock on hand. FIFO needs reliable receipt dates.

## FIFO pick suggestion
A recommendation of which lots to issue first: the oldest eligible lots, excluding expired and blocked stock. It is a suggestion only; nothing is posted to the source system.

## LIFO
Last in, first out is supported only as an operational issue rule when a customer configures it, never as a valuation method unless the customer's policy says so.

## Lot cost
The unit cost recorded on a lot at receipt, which can be compared with the moving average on that date.

## Latest price
Each customer chooses one definition: the latest valid purchase price from purchase records, or the latest receipt cost from stock movements.
