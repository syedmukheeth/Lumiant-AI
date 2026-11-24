# UI/UX Design System

The design system was established in M10 and M11 (ADR-0011): graphite surfaces with an emerald accent, Inter for text and numbers, Geist Mono for identifiers, and a theme that follows the device with a manual toggle. Primitives live in `apps/web/src/components/ui/`, and shared data widgets in `components/data/`. Tokens are CSS variables, with a lint that blocks literal colours. This page records the system and this phase's additions. The brand re-skin (navy and gold) waits for the official logos (`BRAND_IMPLEMENTATION.md`).

## Foundations (existing)

| Element | Where | Notes |
|---|---|---|
| Colour tokens (surface, line, ink, accent, signal, ok) | global CSS, ADR-0011 | contrast-gated in both themes |
| Typography scale (`text-caption`, `text-title`, `text-section`, figures) | Tailwind theme | tabular figures via `.figure`, identifiers via `.code` |
| Controls | `ui/button.tsx` (primary, secondary, ghost, soft; sm/md/lg), `ui/field.tsx` (Field wraps a `<label>`, Input, Select, Textarea, SearchInput) | 3:1 control boundary |
| Status | `ui/badge.tsx` (neutral, accent, signal, ok): states are worded, never colour-only | |
| Layout | `PageHeader`, `Panel` (provenance and Analyst hooks), `Tabs`, `Segmented`, `EmptyState` | |
| Data | `DataTable` (sticky header), `SimpleTable`, `Pager`, `ErrorState` (409 → "Needs more data", 403 → "Not available for your role", others → message plus reference, never a raw exception), `Skeleton` | |
| Shell | rail with groups, command palette (⌘K), shortcuts ("G then key"), Analyst dock and Lens | |

## Navigation (this phase)

| Group | Pages | Shown when |
|---|---|---|
| Monitor | Overview, Explore | `dashboard:read` |
| Analyze | Inventory, Risks, Costs, Assistant | per permission |
| **Plan** | **Orders & materials** (`/planning`, G N) | `inventory:read` and the tenant provides customer orders or BOMs |
| **Procure** | **Supplier comparison** (`/suppliers`, G U) | `cost:read` and the tenant provides supplier–item data |
| Govern | **Item master** (`/master-data`, G M), Reports, Admin | per permission |

Modules without data or permission are not shown, and the server enforces the same rules. Unimplemented modules (capacity, supplier directory, PO review) are not listed.

## New workspace patterns

- **Stat strip:** four `Stat` tiles, each with a definition hint and date context ("planned on …"). A tile only appears when its data exists.
- **Explainable line list** (order fulfilment): one row per order line with a status badge (On time / N working days late / Cannot be dated). The row expands to show the reasons chain; the quantity split is stock / open POs / alternates / to make or buy.
- **Planned-order table:** make or buy badge, release (overdue in signal colour), need, earliest ready, the orders it serves, and the "why" text from the engine.
- **BOM explorer:** an indented tree with subassembly and phantom badges next to a total-requirements list. Engine issues show below.
- **Supplier comparison:** a form for item, quantity, need date and ranking policy (the policy hint explains the weights). A recommendation callout sits above a single table with rank or eligibility, cost per unit needed, order quantity with MOQ excess, earliest delivery with lead days, rejection and on-time percentages with sample size ("insufficient evidence" when fewer than 3 deliveries), price vs last purchase, score and reasons.
- **Recommendation note:** every planning view ends with "Recommendation only …" so no screen implies an action was executed.
- **Planning issues:** blockers ("Cannot calculate: …") and warnings ("Check: …") from the engine, in one list.

## Verified this phase

Browser checks on demo-delta (23 Nov): `/planning` (fulfilment with expanded reasons), `/suppliers` (comparison with ineligible suppliers and unknown charges), `/master-data` (duplicates). Role checks via the API for delta.planner and alpha.

## Not yet done (honest)

WCAG audit with tooling (axe); planning pages at tablet and mobile widths (tables scroll horizontally but have not been reviewed); column selection and export on the planning tables; e2e tests for the new pages; brand tokens and logos.
