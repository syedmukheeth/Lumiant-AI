# Inventory metrics and analyses

Definitions Lumiant uses on every screen and in the assistant. They are draft definitions until the customer approves them; synthetic tenants use them for demonstration.

## Inventory value
Inventory value is the sum of on-hand quantity multiplied by the valuation price the source system provides (for example an ERP moving average). It is always shown per currency: amounts in different currencies are never added together without an approved exchange-rate table. Stock lines without a valuation price are left out of the value and counted in a warning, never treated as zero.

## Quantities and units of measure
Quantities are always shown per unit of measure. Lumiant never adds kilograms to pieces or litres to metres; a total across units needs an approved conversion table, which does not exist yet.

## Below reorder level
An item is below its reorder level in a warehouse when the on-hand quantity there (all stock lines, zero when there are none) is lower than the customer-defined reorder level. Items without a reorder policy are not flagged; they are counted separately as having no policy. Each row shows on-hand, reorder level, shortfall and unit.

## Excess stock
An item has excess stock in a warehouse when its on-hand quantity is above the customer-defined maximum stock level for that item and warehouse. Items without a maximum are not judged.

## Dormant or slow-moving stock
Dormant stock is stock on hand with no issue movement (goods issued to production, sales or consumption) within a chosen number of days before the data date. The default window is 270 days. Receipts and transfers do not count as movement for this check.

## Expiring and expired lots
A lot is expiring when it has stock on hand and its expiry date falls within the chosen number of days from the data date; it is expired when the expiry date has already passed. This needs lot expiry dates to be mapped.

## Value concentration (Pareto, 80/20)
Value concentration shows how few items hold most of the on-hand value, per currency: items are ranked by value and their cumulative share is computed until it reaches the target share (80 percent by default). If the row limit is reached first, the answer says so instead of extrapolating.

## ABC classification
ABC as assigned is the class recorded in the source item master. Computed ABC ranks items by value with thresholds the customer configures; there are no universal thresholds. Both can be shown side by side so differences stand out.

## Data quality checks
Master-data checks count items without a description, item group, ABC class, base unit of measure or inventory stage, stock lines without a valuation price, and stocked item and warehouse pairs without a reorder policy. A check whose field is not mapped is reported as not mapped, not as zero problems.

## Stock status
Stock status describes whether stock can be used: unrestricted (free to use), quality inspection, in transit, restricted, blocked and returns. Value and quantity can be broken down by status.

## Inventory stage
Inventory stage classifies stock as RAW (raw material), SEMI (semi-finished), FINISHED (finished goods) or SPARE (maintenance spares), plus customer-defined stages.

## Special storage requirements
Items can record a minimum and maximum storage temperature and a flammability or hazard class; warehouses can record whether they are temperature controlled or approved for flammable goods. A mismatch is only flagged when both sides are mapped; requirements are never guessed from item names.
