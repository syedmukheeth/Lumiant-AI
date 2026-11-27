# ERP terminology

Customers ask in their own ERP's words. Lumiant maps them to its canonical terms.

## SAP terms
Plant is a warehouse in Lumiant; storage location (LGORT) is a storage location; material is an item; material group is an item group; material type (ROH raw, HALB semi-finished, FERT finished, ERSA spares) is the inventory stage; batch is a lot. MB52 lists warehouse stocks of materials; MB51 is the material document list (movements); MARC holds plant-level material data such as reorder points; MCHB and MCH1 hold batch stock and batch master data; T001W and T001L are the plant and storage location names; EKPO holds purchase order items. Unrestricted-use, quality inspection, blocked and in-transit stock are stock statuses.

## Odoo terms
Warehouse and location keep their names; product is an item; product category is an item group; quants are stock lines; lot or serial number is a lot; reordering rules hold the minimum (reorder level) and maximum quantities.

## Oracle Fusion terms
Inventory organisation is a warehouse; subinventory is a storage location; item category is an item group; on-hand quantity is stock on hand; min-max planning holds the reorder level and maximum.
