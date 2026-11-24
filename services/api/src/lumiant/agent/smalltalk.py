"""Greetings and small talk ("hey", "thanks", "who are you?", "مرحبا") answered directly, in English or Arabic.

Only a message that is *entirely* small talk is answered here: "hi, which items are below reorder level?" still goes
to the analyses. No tool runs, no data is read and nothing is sent to an external model, so a reply never holds a figure.
"""

from __future__ import annotations

import re

from lumiant.agent.terminology import normalize

_ARABIC = re.compile("[؀-ۿ]")
_FILLER = r"(?:\s+(?:there|lumiant|team|all|everyone|bot|assistant|again|so much|a lot|very much|mate|buddy))*"


def _rx(*parts: str) -> re.Pattern[str]:
    """A whole-message pattern; Arabic parts are normalised like the questions are."""
    alts = "|".join(normalize(p) if _ARABIC.search(p) else p for p in parts)
    return re.compile(rf"^(?:{alts}){_FILLER}$")


_INTENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "greeting",
        _rx(
            r"h(i+|ey+|ello+|iya|owdy)",
            r"yo",
            r"sup",
            r"what'?s up",
            r"greetings",
            r"good (morning|afternoon|evening|day)",
            r"(hi|hey|hello) (how are you|how'?s it going)",
            "مرحبا",
            "مرحبا بك",
            "اهلا",
            "اهلا وسهلا",
            "هلا",
            "هاي",
            "السلام عليكم",
            "السلام عليكم ورحمة الله",
            "صباح الخير",
            "مساء الخير",
        ),
    ),
    (
        "how_are_you",
        _rx(r"how are (you|u)( doing)?( today)?", r"how'?s it going", r"how do you do", "كيف حالك", "كيفك", "شلونك"),
    ),
    (
        "thanks",
        _rx(
            r"(ok(ay)?|great|perfect|awesome|nice|cool)?\s*,?\s*(thanks|thank you|thank u|thx|ty|cheers)",
            "شكرا",
            "شكرا لك",
            "شكرا جزيلا",
            "مشكور",
            "يعطيك العافية",
        ),
    ),
    ("bye", _rx(r"(good)?bye", r"see (you|ya)( later)?", r"bye for now", "مع السلامة", "الى اللقاء", "باي")),
    (
        "about",
        _rx(
            r"who are (you|u)",
            r"what are you",
            r"what (can|do) you do",
            r"what can i ask( you)?",
            r"how (can|do) you help( me)?",
            r"how does this work",
            r"help( me)?",
            r"what is lumiant",
            "من انت",
            "ماذا تستطيع ان تفعل",
            "ماذا يمكنك ان تفعل",
            "كيف تساعدني",
            "ساعدني",
            "مساعدة",
        ),
    ),
    (
        "ack",
        _rx(
            r"ok(ay)?",
            r"k",
            r"cool",
            r"great",
            r"nice",
            r"perfect",
            r"awesome",
            r"got it",
            r"sounds good",
            "تمام",
            "حسنا",
            "ممتاز",
        ),
    ),
)

_ABOUT_EN = (
    "I'm Lumiant's inventory assistant. I answer questions about the stock you have access to: what it's worth, where "
    "it is held, what is below reorder level or in excess, what hasn't moved, which lots are expiring, and where the "
    "master data has gaps. You can use your ERP's terms (SAP, Odoo, Oracle) or ask in Arabic. Try one of these:"
)
_ABOUT_AR = (
    "أنا مساعد المخزون في Lumiant. أجيب عن أسئلة المخزون الذي يحق لك الاطلاع عليه: قيمته، وأماكن وجوده، والأصناف "
    "تحت حد إعادة الطلب أو الفائضة، والأصناف الراكدة، والدفعات القريبة من انتهاء الصلاحية، ونواقص البيانات الرئيسية. "
    "جرّب أحد هذه الأسئلة:"
)
_REPLIES: dict[str, tuple[str, str]] = {
    "greeting": (
        "Hi{name}! I'm your inventory assistant. Ask me about stock value, reorder levels, dormant stock, expiring lots "
        "or data quality, or start with one of these:",
        "أهلاً{name}! أنا مساعد المخزون. اسألني عن قيمة المخزون، أو حدود إعادة الطلب، أو الأصناف الراكدة، أو الدفعات "
        "القريبة من انتهاء الصلاحية، أو ابدأ بأحد هذه الأسئلة:",
    ),
    "how_are_you": (
        "Doing well, thanks for asking. What would you like to know about your inventory?",
        "بخير، شكراً لسؤالك. ماذا تريد أن تعرف عن مخزونك؟",
    ),
    "thanks": ("You're welcome. Anything else you'd like to check?", "على الرحب والسعة. هل تريد التحقق من شيء آخر؟"),
    "bye": (
        "Goodbye! Come back any time you need an inventory answer.",
        "مع السلامة! عد متى احتجت إلى إجابة عن المخزون.",
    ),
    "about": (_ABOUT_EN, _ABOUT_AR),
    "ack": ("Great. What would you like to look at next?", "تمام. ماذا تريد أن ترى بعد ذلك؟"),
}


def intent(message: str) -> str | None:
    """The small-talk intent if the whole message is small talk, else None."""
    text = normalize(message.replace("’", "'"))
    text = re.sub(r"[^\w\s']", " ", text)  # punctuation and emoji
    text = " ".join(text.split())
    if not text or len(text) > 60:
        return None
    for key, pattern in _INTENTS:
        if pattern.match(text):
            return key
    return None


def reply(message: str, display_name: str = "") -> str | None:
    """A short reply in the user's language, or None when the message is a real question."""
    key = intent(message)
    if key is None:
        return None
    english, arabic = _REPLIES[key]
    first = display_name.split()[0] if display_name.strip() else ""
    text = arabic if _ARABIC.search(message) else english
    return text.replace("{name}", f" {first}" if first and not _ARABIC.search(message) else "")
