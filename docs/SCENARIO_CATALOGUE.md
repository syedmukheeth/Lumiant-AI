# Scenario Catalogue

Each scenario lists the capability that handles it, its status and the automated check that proves it. Check ids refer to `services/api/evals/scenarios/*.yaml` (harness `tests/unit/test_planning_scenarios.py`) or `tests/integration/test_planning.py` (prefixed `int:`).

**Statuses**
- **Tested**: implemented and tested. Inputs are represented, rules implemented, results correct and explained, permissions enforced, automated test passes.
- **Implemented**: implemented but not fully verified.
- **Partial**: partially implemented.
- **Planned**
- **Blocked**: blocked by unavailable data.

## Customer and order management (1–10)

| # | Scenario | Capability | Status | Evidence |
|---|---|---|---|---|
| 1 | Full order fulfilment | order_fulfilment | Tested | S01 |
| 2 | Partial availability | order_fulfilment, mrp | Tested | S02, S02b |
| 3 | Competing orders, configurable allocation | mrp allocation policy | Tested | S03, S03b, C-B |
| 4 | Urgent order (stock, supplier expedite, partial delivery) | fulfilment + supplier policy `urgent` | Partial | C-A, C-A2. Expedite costs and production re-sequencing are not modelled. |
| 5 | Customer changes quantity (no double count) | mrp (demand = current order state) | Tested | S05 |
| 6 | Cancellation, excess risk | mrp excess_supply | Tested | S06, C-N |
| 7 | Several delivery dates per order | time-phased mrp | Tested | S07 |
| 8 | Partial fulfilment and backorder | fulfilment | Tested | S08 |
| 9 | Customer-specific specifications | alternates with customer restriction | Partial | S45. Item specification compatibility per customer is not modelled. |
| 10 | Customer returns | stock status | Tested | S10 (only unrestricted, company-owned, unexpired stock is usable) |

## Inventory availability and balancing (11–20)

| # | Scenario | Capability | Status | Evidence |
|---|---|---|---|---|
| 11 | Present but unavailable (reserved, blocked, expired, customer-owned) | mrp setup | Tested | S11, S11b, S10 |
| 12 | Stock in other warehouses | transfers | Tested | C-D, C-O |
| 13 | Excess here, shortage there | transfers vs purchase | Tested | C-D (transfer arrives 2026-12-03 vs a 20-day purchase) |
| 14 | Incoming PO not yet arrived | time-phased supply | Tested | S14 |
| 15 | Expiry, FEFO/FIFO | expired stock excluded | Partial | S11b. FEFO lot selection and customer issue policies not built; issue and valuation methods are kept separate (costing module). |
| 16 | Safety stock | protection and replenishment | Partial | S16, S16b. Statistical safety stock (variability, service level) needs history. |
| 17 | Sudden demand increase | re-run with new demand | Partial | Same engine (S05 pattern); no dedicated impact report. |
| 18 | Seasonal demand | forecasting | Planned | `assess` reports a gap (C-J) |
| 19 | Slow-moving and dormant | lifecycle + existing dormant analysis | Tested | S74, existing `dormant` tests |
| 20 | Obsolete or superseded | lifecycle | Tested | S74, C-F, C-K |

## BOM and manufacturing (21–33)

| # | Scenario | Capability | Status | Evidence |
|---|---|---|---|---|
| 21 | Simple BOM explosion | bom | Tested | S21 |
| 22 | Multi-level BOM, cycle detection | bom, mrp | Tested | S22, S22b |
| 23 | Shared raw materials aggregated | mrp (merged planned orders) | Tested | S23, C-B |
| 24 | BOM revision by date | bom.select_bom | Tested | S24, C-F |
| 25 | Missing BOM component | bom, mrp | Tested | S25 |
| 26 | Approved alternative material | mrp substitution | Tested | S26, S26b–d |
| 27 | Scrap and yield | bom | Tested | S27 |
| 28 | Phantom assemblies | bom, mrp | Tested | S28, int: phantom kit |
| 29 | Alternative BOM / method | bom (alternative + priority) | Partial | S29 chooses the preferred alternative. A cost and lead-time comparison across alternatives is not built. |
| 30 | Co-products and by-products | — | Planned | |
| 31 | Rework and repair | — | Planned | |
| 32 | Subcontracting | — | Planned | |
| 33 | Make or buy | supplier comparison + lead time | Partial | No internal cost or capacity model. |

## Production and lead times (34–41)

| # | Scenario | Capability | Status | Evidence |
|---|---|---|---|---|
| 34 | Item-specific manufacturing lead time | policy per item and plant | Tested | S23, C-A |
| 35 | Operation-level routing | — | Planned | No routing data |
| 36 | Insufficient capacity | assess → unsupported | Blocked | C-J. Needs work centres and capacities. |
| 37 | Machine downtime | — | Blocked | Needs maintenance calendars and routings |
| 38 | Working calendars | calendar | Tested | S38 |
| 39 | Minimum run sizes | lot sizing | Tested | S39 |
| 40 | Long supplier lead time → latest release | mrp release, suppliers latest_release | Tested | S38, S63, C-A |
| 41 | Lead-time uncertainty | quoted vs actual on-time % | Partial | Quoted lead time and on-time history are kept separate; variability buffers not built. |

## Alternate items (42–45)

| # | Scenario | Status | Evidence |
|---|---|---|---|
| 42 | Partial substitution with a maximum share | Tested | S42 |
| 43 | Several alternates by priority | Tested | S43 |
| 44 | Alternate also out of stock | Tested | S44 |
| 45 | Similar description but not approved | Tested | S26b, S45, C-A (RM1B not used), S69 different_specification |

## Suppliers and procurement (46–68)

| # | Scenario | Status | Evidence |
|---|---|---|---|
| 46 | Compare suppliers | Tested | C-C, int: supplier comparison |
| 47 | Cheapest has poor quality | Tested | C-C (`quality_critical` excludes SA at 15%) |
| 48 | Cheapest too late | Tested | S48 |
| 49 | Fast but expensive | Tested | C-C (`urgent` vs `lowest_cost` vs `balanced`) |
| 50 | Quote above historical price | Tested | S50, C-G |
| 51 | Price breaks without forced bulk buying | Tested | S51 |
| 52 | MOQ above need | Tested | C-H, S52 |
| 53 | Partial delivery | Tested | C-M (open quantity remains supply) |
| 54 | Repeated delays | Tested | C-G (on-time 25% fails an 80% minimum) |
| 55 | Supplier capacity, split sourcing | Tested | S55 |
| 56 | Expired certificate | Tested | S56, int: SUP-OMEGA |
| 57 | No quality history | Tested | S57 |
| 58 | Several currencies | Tested | S58. No FX dataset in the canonical model yet, so on tenants these offers are marked not comparable. |
| 59 | Landed cost | Tested | S59, C-L (unknown freight disclosed) |
| 60 | No approved supplier | Tested | S60 |
| 61 | Net purchase requirement | Tested | S02, S11, C-M |
| 62 | Existing open PO not re-bought | Tested | S06, S08, S14 |
| 63 | PO release date | Tested | S38, S63 |
| 64 | Split across suppliers | Tested | S55 |
| 65 | Emergency procurement | Tested | C-A (urgent policy picks the approved fast supplier) |
| 66 | Purchase price variance | Tested | S50, C-G |
| 67 | Purchase return | Partial | Rejected quantity is not supply (C-M); return documents not modelled. |
| 68 | Supplier replacement | Partial | Unavailable suppliers drop out (status, approval); no impact report. |

## Item master and lifecycle (69–79)

| # | Scenario | Status | Evidence |
|---|---|---|---|
| 69 | Exact duplicate | Tested | S69 |
| 70 | Similar description, different size | Tested | S69 (D1/D3, D8/D9) |
| 71 | Same product, different supplier codes | Planned | `supplier_item_code` is stored; matching is not built. |
| 72 | Incomplete item master | Partial | `duplicates.missing_attributes` exists, untested; the existing data-quality checks cover core fields. |
| 73 | Conflicting records | Tested | S69 (unit conflict D6/D7) |
| 74 | Dormant, no demand | Tested | S74 |
| 75 | Dormant critical spare | Tested | S74, C-K, int: SP-BEARING-7310 |
| 76 | Superseded item | Tested | C-F, int: RM-STEEL-S1 |
| 77 | Not used in active BOMs | Tested | S74 (O6 active via BOM), C-E |
| 78 | New technology | Planned | No lifecycle source data |
| 79 | Expiring stock actions | Implemented | `obsolescence.review(expiring=…)`, not yet covered by a check |

## Data quality and exceptions (80–89)

| # | Scenario | Status | Evidence |
|---|---|---|---|
| 80 | Missing lead time | Tested | S80, int: RM-COPPER |
| 81 | Missing BOM | Tested | S25, C-I |
| 82 | Missing unit conversion | Tested | S82, C-I |
| 83 | Inconsistent currencies | Tested | S58 |
| 84 | Conflicting balances from two systems | Planned | One source per tenant today |
| 85 | Stale data | Implemented | `PlanningService._load` adds `stale_data`; existing freshness tests cover detection |
| 86 | Schema drift | Tested (existing) | Admin drift check, `test_admin.py` |
| 87 | Unknown fields | Partial (existing) | Admin reports unmapped columns; `nomap` prototype proposes meanings |
| 88 | Invalid relationships | Tested | S25 (unknown component), loader skips unresolved supply |
| 89 | Duplicate transactions | Planned | Source keys are kept; deduplication rules not built |

## Combined scenarios (A–R)

| Id | Scenario | Status | Evidence |
|---|---|---|---|
| A | Urgent order, partial stock, short component, slow supplier, faster alternative | Tested | C-A, C-A2 |
| B | Competing orders for shared materials | Tested | C-B |
| C | Cheapest vs best supplier under different policies | Tested | C-C |
| D | Excess here, shortage there | Tested | C-D |
| E | Duplicate items with BOM references | Tested | C-E |
| F | Redesign with open orders on the old revision | Tested | C-F |
| G | Preferred supplier: price up, late, declining quality | Tested | C-G |
| H | MOQ vs demand | Tested | C-H |
| I | Missing data: what can still be answered | Tested | C-I |
| J | Seasonal demand and capacity | Partial | C-J (reported as unsupported with gaps) |
| K | Critical spare with low movement | Tested | C-K |
| L | Multi-currency landed cost | Tested | C-L |
| M | Partial receipt with rejected goods | Tested | C-M |
| N | Cancellation after procurement | Tested | C-N |
| O | Multi-plant transfer and production dependency | Tested | C-O |
| P | Revenue protection: high-value order, cheap supplier too slow, fast one costs more (plus quality gate and already-on-time variants) | Tested | C-P, C-P2, C-P3; int:test_commitment_protection_on_the_pump_order |
| Q | Fastest supplier lacks quantity: split sourcing meets the date | Tested | C-Q |
| R | No option meets the date: infeasibility with fallbacks (earliest date, partial delivery, alternates) | Tested | C-R |

## Industry and operational extensions (Part 14)

| Topic | Data needed | Status | Fit in the architecture |
|---|---|---|---|
| Project and contract inventory | project/contract id on stock, demand and reservations | Planned | Reservations and owner already modelled; add a `project_id` dimension. |
| Maintenance spares, criticality | equipment–spare links, criticality | Partial | `item.critical` used by lifecycle; equipment links planned. |
| Oil and gas, construction, regulated materials | certifications per item and supplier, batch traceability | Planned | Supplier certificates done; item-level certificates are a new field. |
| Serial and batch traceability, recalls | lot genealogy | Planned | `lot` exists; genealogy needs movement links. |
| Consignment, VMI, customer-owned | stock owner | Partial | `StockLine.owner` excludes non-company stock (S11b). |
| Intercompany, regional balancing | transfer lanes and entities | Partial | Lanes with `allowed` (C-D); entity rules planned. |
| Import procurement, customs delays | customs lead time, duty | Partial | Duty in landed cost; customs time can be part of `receiving_days`. |
| Cold chain, hazardous storage | storage requirements | Tested (existing) | `special_storage` analysis. |
| Quality inspection and rejection | stock status, rejected qty | Tested | S10, C-M |
| Repair, refurbishment, reusable packaging, by-products | routings and co-product BOMs | Planned | |
| Plant shutdowns | calendar holidays per plant | Partial | Calendar holidays exist (tenant-wide); per-plant calendars planned. |
| Emergency demand | urgent policy, priority allocation | Tested | C-A, S03b |
| Replacement parts for discontinued equipment | supersession | Tested | C-F |
