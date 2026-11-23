"""Bill of materials: revision choice, multi-level explosion, scrap and yield, phantoms, cycles (scenarios 21–29).

Gross component quantity for one BOM line:

    parent quantity × line quantity ÷ base quantity × (1 + scrap %) ÷ (yield % of the parent BOM)

Phantom components are exploded through (their own components are required instead); a cycle or a missing BOM for
a make item is reported as a blocker instead of producing a number.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from lumiant.planning.model import HUNDRED, ONE, Bom, Issue, Item, Severity, UomConversion
from lumiant.planning.uom import convert

MAX_LEVELS = 25


@dataclass
class ExplodedLine:
    component_id: str
    quantity: Decimal  # in the component's base unit
    level: int
    path: tuple[str, ...]  # parent chain from the top item
    bom_id: str
    revision: str
    explanation: str
    exploded: bool = False  # True when this line was exploded further (a subassembly or phantom)
    phantom: bool = False


@dataclass
class Explosion:
    item_id: str
    quantity: Decimal
    on: date
    lines: list[ExplodedLine] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    def totals(self, leaves_only: bool = True) -> dict[str, Decimal]:
        """Consolidated requirement per component (shared components added once per path, scenario 23)."""
        out: dict[str, Decimal] = defaultdict(Decimal)
        for ln in self.lines:
            if ln.phantom or (leaves_only and ln.exploded):
                continue
            out[ln.component_id] += ln.quantity
        return dict(out)


def select_bom(boms: tuple[Bom, ...] | list[Bom], item_id: str, on: date, alternative: str | None = None) -> Bom | None:
    """The released BOM valid on `on` (scenario 24): a future revision never applies to an earlier date."""
    return _select_bom(_by_item(boms).get(item_id, ()), item_id, on, alternative)


# BOMs indexed by parent item, per BOM collection (identity-checked; a run plans against one collection).
_INDEX: dict[int, tuple[object, dict[str, list[Bom]]]] = {}


def _by_item(boms: tuple[Bom, ...] | list[Bom]) -> dict[str, list[Bom]]:
    hit = _INDEX.get(id(boms))
    if hit is not None and hit[0] is boms and isinstance(boms, tuple):
        return hit[1]
    index: dict[str, list[Bom]] = defaultdict(list)
    for bom in boms:
        index[bom.item_id].append(bom)
    if isinstance(boms, tuple):  # lists can change in place, so only immutable collections are cached
        if len(_INDEX) > 16:
            _INDEX.clear()
        _INDEX[id(boms)] = (boms, index)
    return index


def _select_bom(boms: tuple[Bom, ...] | list[Bom], item_id: str, on: date, alternative: str | None) -> Bom | None:
    valid = [b for b in boms if b.item_id == item_id and b.valid_on(on)]
    if alternative is not None:
        valid = [b for b in valid if b.alternative == alternative]
    if not valid:
        return None
    return sorted(valid, key=lambda b: (b.priority, b.alternative, b.valid_from or date.min), reverse=False)[0]


def component_quantity(parent_qty: Decimal, bom: Bom, line_qty: Decimal, scrap_pct: Decimal) -> Decimal:
    gross = parent_qty * line_qty / bom.base_quantity * (ONE + scrap_pct / HUNDRED)
    return gross / (bom.yield_pct / HUNDRED)


def explode(
    item_id: str,
    quantity: Decimal,
    on: date,
    boms: tuple[Bom, ...] | list[Bom],
    items: dict[str, Item],
    conversions: tuple[UomConversion, ...] = (),
    *,
    single_level: bool = False,
) -> Explosion:
    result = Explosion(item_id, quantity, on)
    _explode(item_id, quantity, on, boms, items, conversions, result, (item_id,), 1, single_level)
    return result


def _explode(
    item_id: str,
    quantity: Decimal,
    on: date,
    boms: tuple[Bom, ...] | list[Bom],
    items: dict[str, Item],
    conversions: tuple[UomConversion, ...],
    result: Explosion,
    path: tuple[str, ...],
    level: int,
    single_level: bool,
) -> None:
    if level > MAX_LEVELS:
        result.issues.append(
            Issue("bom_too_deep", Severity.BLOCKER, f"BOM of {item_id} is deeper than {MAX_LEVELS} levels.", item_id)
        )
        return
    bom = select_bom(boms, item_id, on)
    if bom is None:
        item = items.get(item_id)
        if (item is not None and item.procurement in ("make", "both")) or level == 1:
            result.issues.append(
                Issue(
                    "missing_bom",
                    Severity.BLOCKER,
                    f"No released BOM of {item_id} is valid on {on.isoformat()}; "
                    "its material requirements cannot be planned.",
                    item_id,
                )
            )
        return
    for line in sorted(bom.lines, key=lambda ln: ln.sequence):
        comp = line.component_id
        if comp in path:
            result.issues.append(
                Issue(
                    "bom_cycle",
                    Severity.BLOCKER,
                    f"Circular BOM: {' → '.join((*path, comp))}. Explosion stopped on this branch.",
                    comp,
                    bom.bom_id,
                )
            )
            continue
        comp_item = items.get(comp)
        if comp_item is None:
            result.issues.append(
                Issue(
                    "unknown_component",
                    Severity.BLOCKER,
                    f"BOM {bom.bom_id} rev {bom.revision} references {comp}, which is not in the item master.",
                    comp,
                    bom.bom_id,
                )
            )
            continue
        if comp_item.status.upper() in ("BLOCKED", "INACTIVE", "DELETED"):
            result.issues.append(
                Issue(
                    "inactive_component",
                    Severity.WARNING,
                    f"Component {comp} of {item_id} has status {comp_item.status}.",
                    comp,
                    bom.bom_id,
                )
            )
        line_qty = line.quantity
        if line.uom and line.uom != comp_item.base_uom:
            converted = convert(line.quantity, line.uom, comp_item.base_uom, comp, conversions)
            if converted is None:
                result.issues.append(
                    Issue(
                        "missing_uom_conversion",
                        Severity.BLOCKER,
                        f"BOM {bom.bom_id} uses {line.uom} for {comp} but its base unit is {comp_item.base_uom} "
                        "and no conversion exists.",
                        comp,
                        bom.bom_id,
                    )
                )
                continue
            line_qty = converted
        qty = component_quantity(quantity, bom, line_qty, line.scrap_pct)
        why = f"{quantity} × {line_qty} / {bom.base_quantity}"
        if line.scrap_pct:
            why += f" × (1 + {line.scrap_pct}% scrap)"
        if bom.yield_pct != HUNDRED:
            why += f" / {bom.yield_pct}% yield"
        exploded = ExplodedLine(
            comp, qty, level, path, bom.bom_id, bom.revision, f"{why} = {qty.normalize():f}", phantom=comp_item.phantom
        )
        result.lines.append(exploded)
        if comp_item.phantom or (not single_level and comp_item.procurement in ("make", "both")):
            exploded.exploded = True
            _explode(comp, qty, on, boms, items, conversions, result, (*path, comp), level + 1, single_level)


def low_level_codes(boms: tuple[Bom, ...] | list[Bom]) -> tuple[dict[str, int], list[Issue]]:
    """Deepest level at which each item appears in any released BOM; cycles are reported, not followed."""
    children: dict[str, set[str]] = defaultdict(set)
    for b in boms:
        if b.status == "released":
            for ln in b.lines:
                children[b.item_id].add(ln.component_id)
    codes: dict[str, int] = defaultdict(int)
    issues: list[Issue] = []
    seen_cycles: set[tuple[str, ...]] = set()

    def walk(node: str, depth: int, path: tuple[str, ...]) -> None:
        if depth > MAX_LEVELS:
            return
        for child in children.get(node, ()):
            if child in path:
                cyc = (*path[path.index(child) :], child)
                if cyc not in seen_cycles:
                    seen_cycles.add(cyc)
                    issues.append(Issue("bom_cycle", Severity.BLOCKER, "Circular BOM: " + " → ".join(cyc), child))
                continue
            if depth + 1 > codes[child]:
                codes[child] = depth + 1
            walk(child, depth + 1, (*path, child))

    for top in list(children):
        codes.setdefault(top, 0)
        walk(top, codes[top], (top,))
    return dict(codes), issues


def where_used(boms: tuple[Bom, ...] | list[Bom], component_id: str, on: date | None = None) -> list[Bom]:
    """Released BOMs (valid on `on` when given) that use `component_id` directly (scenario 77)."""
    return [
        b
        for b in boms
        if (b.valid_on(on) if on else b.status == "released") and any(ln.component_id == component_id for ln in b.lines)
    ]
