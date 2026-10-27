"""Configurable item-code parsing/validation. Segment meaning is tenant configuration, never assumed."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from lumiant.tenancy.models import ItemCoding


@dataclass(frozen=True)
class ParsedCode:
    code: str
    valid: bool
    segments: dict[str, str] = field(default_factory=dict)
    problems: tuple[str, ...] = ()


def parse_item_code(code: str | None, coding: ItemCoding) -> ParsedCode:
    if code is None or code == "":
        return ParsedCode(code or "", False, problems=("empty_code",))
    problems: list[str] = []
    if re.fullmatch(coding.pattern, code) is None:
        problems.append("pattern_mismatch")
    segments: dict[str, str] = {}
    for seg in coding.segments:
        value = code[seg.start : seg.start + seg.length]
        if len(value) < seg.length:
            problems.append(f"segment_missing:{seg.name}")
            continue
        segments[seg.name] = value
        if seg.allowed is not None and value not in seg.allowed:
            problems.append(f"segment_not_allowed:{seg.name}")
    return ParsedCode(code, not problems, segments, tuple(problems))
