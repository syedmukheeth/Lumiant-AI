from decimal import Decimal

from lumiant.agent.grounding import collect_numbers, normalize, ungrounded_numbers


def test_normalize_is_format_insensitive() -> None:
    assert normalize("2,767,451.8300") == "2767451.83"
    assert normalize("10.0000") == "10"
    assert normalize("-0.0") == "0"
    assert normalize("abc") is None


def test_collect_numbers_walks_structures_and_strings() -> None:
    found = collect_numbers(
        {"a": "USD 1,234.50", "b": [Decimal("7.0"), 3], "c": {"d": "item 0012"}, "e": None, "f": True}
    )
    assert {"1234.5", "7", "3", "12"} <= found


def test_ungrounded_numbers_are_detected() -> None:
    evidence = collect_numbers({"qty": "17.0000", "total": 3})
    assert ungrounded_numbers("17 units across 3 warehouses", evidence) == []
    assert ungrounded_numbers("About 18 units across 3 warehouses", evidence) == ["18"]
    # a derived sum is not evidence unless it appears in the results
    assert ungrounded_numbers("17 plus 3 is 20", evidence) == ["20"]


def test_zero_and_one_are_allowed_as_words() -> None:
    assert ungrounded_numbers("There is 1 item and 0 problems", set()) == []
