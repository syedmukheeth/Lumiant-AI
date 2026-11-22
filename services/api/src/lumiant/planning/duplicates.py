"""Item-master duplicate detection (docs/ITEM_MASTER_QUALITY_AND_OBSOLESCENCE.md, scenarios 69–73).

Pairs are compared on normalised description, manufacturer part number and technical attributes. Numbers in the
description (sizes, ratings, grades) and differing attribute values mean *different products* — similar wording is
never enough (scenario 70). Every finding says why; nothing is merged, renamed or deleted.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import combinations

from lumiant.planning.model import Item

_ABBREV = {
    "STAINLESS STEEL": "SS",
    "S/S": "SS",
    "MILLIMETER": "MM",
    "MILLIMETRE": "MM",
    "INCH": "IN",
    '"': " IN",
    "PIECE": "PC",
    "PCS": "PC",
}
_NUM = re.compile(r"\d+(?:[.,/]\d+)?")
SPEC_KEYS = ("size", "grade", "material", "rating", "colour", "length", "diameter", "pressure", "voltage")


def normalize(text: str) -> str:
    t = text.upper()
    for k, v in _ABBREV.items():
        t = t.replace(k, v)
    t = re.sub(r"[^A-Z0-9./ ]+", " ", t)
    t = re.sub(r"(\d)\s+(MM|IN|M|KG|L|BAR|V)\b", r"\1\2", t)
    return " ".join(t.split())


def numbers(text: str) -> tuple[str, ...]:
    return tuple(sorted(n.replace(",", ".") for n in _NUM.findall(text)))


@dataclass
class DuplicateFinding:
    item_a: str
    item_b: str
    verdict: str  # probable_duplicate, possible_duplicate, conflict, different_specification
    confidence: str  # high, medium, low
    similarity: float
    reasons: list[str] = field(default_factory=list)
    action: str = "Review in the item master; nothing has been changed."


def compare(a: Item, b: Item) -> DuplicateFinding | None:
    na, nb = normalize(a.description), normalize(b.description)
    sim = round(SequenceMatcher(None, na, nb).ratio(), 3)
    reasons: list[str] = []
    same_mpn = bool(a.mpn and b.mpn and a.mpn.replace("-", "").upper() == b.mpn.replace("-", "").upper())
    same_maker = bool(a.manufacturer and a.manufacturer.upper() == b.manufacturer.upper())
    diff_attrs = [
        k
        for k in SPEC_KEYS
        if a.attributes.get(k) and b.attributes.get(k) and a.attributes[k].upper() != b.attributes[k].upper()
    ]
    num_a, num_b = numbers(na), numbers(nb)
    if same_mpn:
        reasons.append(f"same manufacturer part number {a.mpn}" + (f" ({a.manufacturer})" if same_maker else ""))
    if na == nb:
        reasons.append("identical normalised description")
    elif sim >= 0.85:
        reasons.append(f"descriptions {int(sim * 100)}% similar")
    if not reasons:
        return None
    if diff_attrs or (num_a != num_b and not same_mpn):
        why = []
        if diff_attrs:
            why += [f"{k}: {a.attributes[k]} vs {b.attributes[k]}" for k in diff_attrs]
        if num_a != num_b:
            why.append(f"different numbers in the description ({' '.join(num_a) or '-'} vs {' '.join(num_b) or '-'})")
        if same_mpn:
            return DuplicateFinding(
                a.item_id,
                b.item_id,
                "conflict",
                "medium",
                sim,
                [*reasons, "but " + "; ".join(why)],
                "Same part number with contradicting attributes: correct the master data after review.",
            )
        return DuplicateFinding(
            a.item_id,
            b.item_id,
            "different_specification",
            "low",
            sim,
            [*reasons, "but " + "; ".join(why)],
            "Similar wording but a different specification: not a duplicate, do not substitute.",
        )
    if a.base_uom and b.base_uom and a.base_uom != b.base_uom:
        return DuplicateFinding(
            a.item_id,
            b.item_id,
            "conflict",
            "medium",
            sim,
            [*reasons, f"but units differ ({a.base_uom} vs {b.base_uom})"],
            "Possibly the same product kept in different units: review before any change.",
        )
    if same_mpn or na == nb:
        return DuplicateFinding(a.item_id, b.item_id, "probable_duplicate", "high", sim, reasons)
    return DuplicateFinding(a.item_id, b.item_id, "possible_duplicate", "medium", sim, reasons)


def find_duplicates(items: list[Item], *, include_different: bool = False) -> list[DuplicateFinding]:
    """Compare items that share a block (MPN, item group or first description word) to stay near-linear."""
    blocks: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        if it.mpn:
            blocks["mpn:" + it.mpn.replace("-", "").upper()].append(it)
        first = normalize(it.description).split(" ")[0] if it.description else ""
        blocks[f"g:{it.item_group}:{first}"].append(it)
    seen: set[tuple[str, str]] = set()
    out: list[DuplicateFinding] = []
    for group in blocks.values():
        if len(group) > 500:
            group = group[:500]
        for a, b in combinations(sorted(group, key=lambda i: i.item_id), 2):
            pair = (a.item_id, b.item_id)
            if pair in seen:
                continue
            seen.add(pair)
            f = compare(a, b)
            if f and (include_different or f.verdict != "different_specification"):
                out.append(f)
    order = {"probable_duplicate": 0, "conflict": 1, "possible_duplicate": 2, "different_specification": 3}
    return sorted(out, key=lambda f: (order[f.verdict], -f.similarity, f.item_a, f.item_b))


def missing_attributes(items: list[Item], required: dict[str, tuple[str, ...]]) -> dict[str, list[str]]:
    """Critical attributes missing per item (scenario 72); `required` maps an item group ('*' = all) to keys."""
    out: dict[str, list[str]] = {}
    for it in items:
        keys = (*required.get("*", ()), *required.get(it.item_group, ()))
        missing = [k for k in keys if not (getattr(it, k, None) if hasattr(it, k) else it.attributes.get(k))]
        if missing:
            out[it.item_id] = missing
    return out
