"""Small talk: greetings and thanks get a direct reply; anything with a real question goes to the analyses."""

from __future__ import annotations

import re

import pytest

from lumiant.agent.smalltalk import intent, reply


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("hey", "greeting"),
        ("Hey!", "greeting"),
        ("hello there", "greeting"),
        ("hii", "greeting"),
        ("Good morning", "greeting"),
        ("what’s up", "greeting"),
        ("hi 👋", "greeting"),
        ("How are you?", "how_are_you"),
        ("thanks", "thanks"),
        ("Thank you so much", "thanks"),
        ("ok thanks", "thanks"),
        ("bye", "bye"),
        ("Who are you?", "about"),
        ("What can you do?", "about"),
        ("help", "about"),
        ("ok", "ack"),
        ("مرحبا", "greeting"),
        ("السلام عليكم", "greeting"),
        ("أهلاً", "greeting"),
        ("صباح الخير", "greeting"),
        ("كيف حالك؟", "how_are_you"),
        ("شكراً", "thanks"),
        ("مع السلامة", "bye"),
        ("من أنت؟", "about"),
    ],
)
def test_small_talk_is_recognised(message: str, expected: str) -> None:
    assert intent(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "hi, which items are below reorder level?",
        "hello show inventory value by warehouse",
        "help me find dormant stock",
        "thanks, now show expiring lots",
        "مرحبا كم قيمة المخزون؟",
        "Which items are in excess?",
        "",
    ],
)
def test_real_questions_are_not_small_talk(message: str) -> None:
    assert intent(message) is None


def test_reply_uses_the_users_language_and_first_name_and_holds_no_figures() -> None:
    english = reply("hey", "Alex Admin")
    arabic = reply("مرحبا", "Alex Admin")
    assert english is not None
    assert english.startswith("Hi Alex!")
    assert arabic is not None
    assert arabic.startswith("أهلاً!")
    for message in ("hey", "thanks", "who are you", "bye", "ok", "مرحبا", "شكرا", "من انت"):
        text = reply(message)
        assert text is not None
        assert not re.search(r"\d", text), message
