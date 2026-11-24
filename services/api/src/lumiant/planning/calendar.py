"""Working-day arithmetic (scenario 38): weekends and holidays are not working days."""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

from lumiant.planning.model import Calendar

MAX_DAYS = 3650


def is_working(day: date, cal: Calendar) -> bool:
    return day.weekday() not in cal.weekend and day not in cal.holidays


@lru_cache(maxsize=65536)  # Calendar is frozen and hashable; MRP repeats the same arithmetic a lot
def add_working_days(start: date, days: int, cal: Calendar) -> date:
    """The date `days` working days after `start` (0 → `start`, or the next working day if `start` is not one)."""
    day = start
    while not is_working(day, cal):
        day += timedelta(days=1)
    remaining = days
    guard = 0
    while remaining > 0:
        day += timedelta(days=1)
        if is_working(day, cal):
            remaining -= 1
        guard += 1
        if guard > MAX_DAYS:
            raise ValueError("calendar has no working days")
    return day


@lru_cache(maxsize=65536)
def subtract_working_days(end: date, days: int, cal: Calendar) -> date:
    """The latest date from which `days` working days still finish by `end` (scenarios 40, 63)."""
    day = end
    while not is_working(day, cal):
        day -= timedelta(days=1)
    remaining = days
    guard = 0
    while remaining > 0:
        day -= timedelta(days=1)
        if is_working(day, cal):
            remaining -= 1
        guard += 1
        if guard > MAX_DAYS:
            raise ValueError("calendar has no working days")
    return day


def working_days_between(start: date, end: date, cal: Calendar) -> int:
    """Working days after `start` up to and including `end` (negative when `end` is earlier)."""
    if end < start:
        return -working_days_between(end, start, cal)
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        if is_working(day, cal):
            count += 1
    return count
