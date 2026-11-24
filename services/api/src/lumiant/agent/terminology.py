"""Inventory terminology across SAP, Odoo, Oracle Fusion, plain English and Arabic.

The assistant reasons in Lumiant's canonical terms (warehouse, storage location, item group, reorder level, …).
Customers ask in their own ERP's words ("plant", "subinventory", "quants", "MB52") or in Arabic. This module maps
those words to the canonical terms so the built-in matcher and any approved LLM understand them.

It holds meanings only, never figures: stock levels, prices and values always come from the customer's data
through the tools.

Sources: curated by Lumiant from public ERP terminology. Arabic terms are common business Arabic, cross-checked
against Odoo 18's stock-module Arabic translations (odoo/odoo, addons/stock/i18n/ar.po, LGPL-3), for example
المخزون (stock), الكمية في اليد (on hand), المستودع (warehouse), الموقع (location), رقم الدفعة (lot number),
قواعد إعادة الطلب (reordering rules), فئة المنتج (product category), تقييم المخزون (inventory valuation).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ------------------------------------------------------------------------------------------ Arabic normalisation
_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭ]")
_LETTERS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
        "،": ",",
        "؟": "?",
        "؛": ";",
        "ـ": "",  # tatweel
    }
)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def ascii_digits(text: str) -> str:
    """Arabic-Indic and Persian digits → 0-9, so item codes and numbers typed in Arabic still resolve."""
    return text.translate(_DIGITS)


def normalize(text: str) -> str:
    """Lower-case, digits to ASCII, and Arabic spelling variants unified (alef forms, ya, ta marbuta, diacritics)."""
    text = _DIACRITICS.sub("", ascii_digits(text)).translate(_LETTERS)
    return " ".join(text.lower().split())


def _ar(*patterns: str) -> tuple[re.Pattern[str], ...]:
    # Arabic spelling normalised like the questions; no lower-casing, which would turn \S into \s.
    return tuple(re.compile(_DIACRITICS.sub("", p).translate(_LETTERS)) for p in patterns)


def _en(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p) for p in patterns)


# ------------------------------------------------------------------------------------------ concepts
@dataclass(frozen=True)
class Concept:
    key: str
    hint: str  # canonical English the matcher and models understand; "" = glossary only
    meaning: str
    erp: str  # how the main systems name it
    en: tuple[re.Pattern[str], ...] = ()
    ar: tuple[re.Pattern[str], ...] = ()


CONCEPTS: tuple[Concept, ...] = (
    Concept(
        "warehouse",
        "warehouse",
        "a site or plant that holds stock",
        "SAP plant (WERKS) · Odoo warehouse (stock.warehouse) · Oracle Fusion inventory organization",
        _en(r"\bplants?\b", r"\bwerks\b", r"inventory org(anization|anisation)?s?\b"),
        _ar(r"مستودع", r"مخزن", r"مخازن", r"\bمصنع"),
    ),
    Concept(
        "location",
        "storage location",
        "a place inside a warehouse: storage location, subinventory, bin or locator",
        "SAP storage location (LGORT) · Odoo location (stock.location, e.g. WH/Stock) · Oracle Fusion subinventory / locator",
        _en(r"\bsubinventor(y|ies)\b", r"\blocators?\b", r"\bbins?\b", r"\blgort\b", r"\bwh/stock\b"),
        _ar(r"موقع", r"مواقع", r"\bرف\b", r"رفوف"),
    ),
    Concept(
        "item",
        "",
        "a stocked product: item, material, product, SKU or article",
        "SAP material (MATNR) · Odoo product (product.product / product.template) · Oracle Fusion item (EGP_SYSTEM_ITEMS_B)",
        _en(r"\bskus?\b", r"\bmatnr\b", r"\bmaterials?\b", r"\barticles?\b"),
        _ar(r"صنف", r"اصناف", r"منتج", r"\bماده\b", r"\bمواد\b"),
    ),
    Concept(
        "item_group",
        "item group",
        "a grouping of items such as material group or product category",
        "SAP material group (MATKL) · Odoo product category · Oracle Fusion item category",
        _en(r"material group", r"\bmatkl\b", r"product categor(y|ies)", r"item categor(y|ies)"),
        _ar(r"فئه المنتج", r"فيه المنتج", r"فئات المنتجات", r"مجموعه الاصناف", r"مجموعه المواد", r"فئه الصنف"),
    ),
    Concept(
        "stage",
        "material type",
        "the item's stage or type: raw material, semi-finished, finished, spare",
        "SAP material type (MTART) · Odoo product type / category · Oracle Fusion item type",
        _en(r"\bmtart\b", r"item type"),
        _ar(r"مواد خام", r"ماده خام", r"منتجات تامه", r"نوع الماده", r"قطع غيار"),
    ),
    Concept(
        "stock_status",
        "stock status",
        "usable versus restricted stock: unrestricted, quality inspection, blocked",
        "SAP LABST / INSME / SPEME · Odoo location usage and quality checks · Oracle Fusion material status",
        _en(
            r"\blabst\b",
            r"\binsme\b",
            r"\bspeme\b",
            r"material status",
            r"value in qual",
            r"restricted[- ]use",
            r"transit and transfer",
        ),
        _ar(r"حاله المخزون", r"غير مقيد", r"\bمقيد", r"فحص الجوده", r"تحت الفحص", r"محظور", r"مجمد"),
    ),
    Concept(
        "on_hand",
        "stock",
        "the quantity physically held",
        "SAP unrestricted stock (MARD-LABST) · Odoo quants (stock.quant) · Oracle Fusion on-hand quantity (INV_ONHAND_QUANTITIES_DETAIL)",
        _en(r"\bquants?\b", r"\bmb52\b", r"\bmmbe\b"),
        _ar(r"الكميه في اليد", r"الكميه المتاحه", r"رصيد المخزون", r"مخزون", r"الكميه"),
    ),
    Concept(
        "value",
        "inventory value",
        "on-hand quantity multiplied by the valuation price, per currency",
        "SAP stock value (MBEW-SALK3) · Odoo inventory valuation (stock.valuation.layer) · Oracle Fusion inventory valuation",
        _en(
            r"\bvaluation\b(?! (class|type))", r"stock value", r"\bsalk3\b", r"on[- ]hand value", r"value unrestricted"
        ),
        _ar(r"قيمه", r"تقييم"),
    ),
    Concept(
        "total",
        "total",
        "the overall figure across everything in scope",
        "",
        (),
        _ar(r"اجمالي", r"مجموع"),
    ),
    Concept(
        "reorder",
        "below reorder level",
        "items whose stock has fallen below the customer's reorder point or minimum",
        "SAP reorder point (MARC-MINBE) · Odoo reordering rule minimum · Oracle Fusion min-max planning minimum",
        _en(
            r"reorder point",
            r"\bminbe\b",
            r"min[- ]max minimum",
            r"below (their |the )?min(imum)?\b",
            r"minimum (stock|qty|quantity)",
            r"\breplenish",
            r"\brun(ning)? out\b",
            r"out of stock",
            r"stock[- ]?outs?\b",
        ),
        _ar(r"اعاده الطلب", r"حد الطلب", r"الحد الادني", r"تحت الحد", r"نفاد", r"نفد", r"تجديد المخزون"),
    ),
    Concept(
        "excess",
        "excess stock",
        "items held above their maximum stock policy",
        "SAP maximum stock level (MARC-MABST) · Odoo reordering rule maximum · Oracle Fusion min-max maximum",
        _en(
            r"\bmabst\b",
            r"max(imum)? (stock|qty|quantity|level)",
            r"min[- ]max maximum",
            r"\bexceed",
            r"above (their |the )?max",
            r"over (their |the )?max",
            r"over[- ]?stock",
            r"(rule|policy) max(imum)?\b",
        ),
        _ar(r"فايض", r"فائض", r"مخزون زايد", r"الكميه القصوي", r"الحد الاقصي", r"اكثر من الحد"),
    ),
    Concept(
        "dormant",
        "not moved",
        "stock with no issue movement for a period: dormant, slow-moving or dead stock",
        "SAP dead/slow-moving stock (MC50, MC46) · Odoo stock with no outgoing moves · Oracle Fusion items with no material transactions",
        _en(
            r"dead stock",
            r"non[- ]moving",
            r"slow movers?",
            r"no (goods )?issues?\b",
            r"no (material )?transactions?\b",
            r"no consumption",
            r"\bmc50\b",
            r"\bmc46\b",
            r"inactive stock",
        ),
        _ar(r"راكد", r"بطي", r"لم يتحرك", r"بدون حركه", r"لا حركه", r"لم تتحرك"),
    ),
    Concept(
        "expiry",
        "expiry",
        "lots or batches that are expired or close to their expiry date",
        "SAP shelf-life expiration date (MCH1-VFDAT, MB5M) · Odoo lot expiration date · Oracle Fusion lot expiration date",
        _en(r"\bvfdat\b", r"\bmb5m\b", r"\bsled\b", r"\bbbd\b"),
        _ar(r"صلاحي", r"انتهاء", r"تنتهي", r"منتهي"),
    ),
    Concept(
        "lot",
        "lots",
        "a batch or lot of an item, tracked for expiry and traceability",
        "SAP batch (CHARG, MCH1) · Odoo lot / serial (stock.lot) · Oracle Fusion lot / serial number",
        _en(r"\bbatch(es)?\b", r"\bcharg\b", r"\bserial numbers?\b"),
        _ar(r"دفعه", r"دفعات", r"تشغيله", r"الرقم التسلسلي"),
    ),
    Concept(
        "data_quality",
        "incomplete master data",
        "gaps in item, price or policy master data that limit the analyses",
        "SAP material master · Odoo product records · Oracle Fusion item master",
        _en(r"item master", r"material master"),
        _ar(
            r"البيانات الرئيسية",
            r"بيانات\S*\s+(ال)?رئيسي",
            r"بيانات\S*\s+ناقص",
            r"(ال)?رئيسية ناقصة",
            r"جودة البيانات",
            r"بيانات غير مكتملة",
        ),
    ),
    Concept(
        "special_storage",
        "special storage",
        "items that need controlled conditions: temperature range, flammability, hazardous goods",
        "SAP temperature conditions / hazardous material number · Odoo storage categories · Oracle Fusion hazard class",
        _en(r"dangerous goods", r"\bhazmat\b", r"cold chain", r"refrigerat"),
        _ar(r"تخزين\S*\s+(ال)?خاص", r"مواد خطره", r"درجه الحراره", r"قابل للاشتعال", r"مبرد"),
    ),
    Concept(
        "top_value",
        "highest-value items",
        "the items holding the most on-hand value",
        "",
        (),
        _ar(r"اعلي قيمه", r"الاعلي قيمه", r"الاكثر قيمه", r"اغلي"),
    ),
    Concept(
        "pareto",
        "pareto",
        "how few items hold most of the value (Pareto or ABC concentration)",
        "",
        (),
        _ar(r"باريتو", r"معظم قيمه", r"معظم القيمه"),
    ),
    Concept(
        "insights",
        "what should i look at",
        "the most important findings across the analyses",
        "",
        (),
        _ar(r"يجب ان انظر", r"يحتاج انتباه", r"تحتاج انتباه", r"اهم الملاحظات", r"\bملخص"),
    ),
    Concept(
        "cost",
        "average cost",
        "how one item is costed: moving average, FIFO, latest receipt or purchase price",
        "SAP moving average price (VERPR) / standard price (STPRS) · Odoo cost (standard_price) · Oracle Fusion item cost",
        _en(r"moving average price", r"standard price", r"\bverpr\b", r"\bstprs\b", r"item cost"),
        _ar(r"تكلفه", r"متوسط التكلفه", r"سعر الشراء", r"اخر سعر"),
    ),
    Concept(
        "classifications",
        "classifications",
        "the classifications in use: ABC class, item group and stage",
        "",
        (),
        _ar(r"التصنيفات"),
    ),
    # Arabic question words and connectors: they carry the intent that English expresses with "how much", "by" …
    Concept("how_many", "how many", "", "", (), _ar(r"كم عدد")),
    Concept("how_much", "how much", "", "", (), _ar(r"\bكم\b")),
    Concept("show", "show", "", "", (), _ar(r"\bاعرض", r"\bاظهر", r"\bعرض\b", r"\bاريد")),
    Concept("by", "by", "", "", (), _ar(r"\bحسب\b", r"\bلكل\b", r"\bبحسب\b", r"موزع")),
    Concept("which", "which", "", "", (), _ar(r"\bما\b", r"\bماهي\b", r"\bاي\b")),
    Concept("compare", "compare", "", "", (), _ar(r"قارن", r"مقارنه", r"\bمقابل\b")),
    Concept("where", "where", "", "", (), _ar(r"\bاين\b", r"في اي مستودع")),
)

_DIMENSION_KEYS = {"warehouse", "location", "item_group", "stage", "stock_status"}
_ABC_AR = re.compile(r"(?:فيه|فئه|تصنيف|الفيه|الفئه)\s*(ا|ب|ج|a|b|c)\b")
_ABC_LETTER = {"ا": "a", "ب": "b", "ج": "c", "a": "a", "b": "b", "c": "c"}
_CODE = re.compile(r"\b\d{5,}\b")
# durations in Arabic → English that parse_days understands ("ستة أشهر" → "6 months")
_AR_NUM = {
    "واحد": 1, "واحده": 1, "اثنين": 2, "اثنان": 2, "ثلاث": 3, "ثلاثه": 3, "اربع": 4, "اربعه": 4, "خمس": 5,
    "خمسه": 5, "ست": 6, "سته": 6, "سبع": 7, "سبعه": 7, "ثماني": 8, "ثمانيه": 8, "تسع": 9, "تسعه": 9,
    "عشر": 10, "عشره": 10,
}  # fmt: skip
_AR_UNIT = (
    (r"يوما|يوم|ايام", "days"),
    (r"اسبوعا|اسبوع|اسابيع", "weeks"),
    (r"شهرا|شهر|اشهر|شهور", "months"),
    (r"سنه|سنوات|عاما|عام|اعوام", "years"),
)
_AR_DUAL = {"يومين": "2 days", "اسبوعين": "2 weeks", "شهرين": "2 months", "سنتين": "2 years", "عامين": "2 years"}


def _durations(text: str) -> list[str]:
    found: list[str] = []
    for word, phrase in _AR_DUAL.items():
        if word in text:
            found.append(phrase)
    for unit_re, unit in _AR_UNIT:
        for m in re.finditer(rf"(\d{{1,4}}|{'|'.join(_AR_NUM)})\s+(?:{unit_re})\b", text):
            n = m.group(1)
            found.append(f"{n if n.isdigit() else _AR_NUM[n]} {unit}")
        if re.search(rf"(?:خلال|منذ|اخر|لمده)\s+(?:ال)?(?:{unit_re})\b", text):
            found.append(f"1 {unit}")
    return found


def matched(question: str) -> list[Concept]:
    """Concepts named in the question, in table order."""
    q = normalize(question)
    return [c for c in CONCEPTS if any(p.search(q) for p in c.en) or any(p.search(q) for p in c.ar)]


def expand(question: str) -> str:
    """The normalised question plus canonical English hints for every ERP or Arabic term it uses.

    "unrestricted stock by plant" → "… :: warehouse; stock status"; "كم قيمة المخزون؟" → "… :: how much; inventory value; …".
    The original words stay first, so anything the matcher already understood still matches as before.
    """
    q = normalize(question)
    concepts = matched(question)
    keys = {c.key for c in concepts}
    hints = [c.hint for c in concepts if c.hint]
    m = _ABC_AR.search(q)
    if m:
        hints.append(f"{_ABC_LETTER[m.group(1)]}-category items")
    hints += _durations(q)
    has_code = bool(_CODE.search(q))
    asks_amount = bool(keys & {"how_much", "how_many"}) or re.search(r"\bhow (much|many)\b", q) is not None
    if asks_amount and keys & {"on_hand", "value"} and not keys & _DIMENSION_KEYS:
        hints.append("how much stock of item" if has_code else "how much inventory do we have")
    if "where" in keys and has_code:
        hints.append("where is the item held")
    return f"{q} :: {'; '.join(dict.fromkeys(hints))}" if hints else q


def glossary_note(question: str, limit: int = 6) -> str:
    """A short glossary of the ERP or Arabic terms in the question, for a model's system prompt. Meanings only."""
    lines = [
        f"- {c.key.replace('_', ' ')}: {c.meaning}" + (f" ({c.erp})" if c.erp else "")
        for c in matched(question)
        if c.meaning
    ][:limit]
    if not lines:
        return ""
    return (
        " Terminology in this question (customers use their ERP's or Arabic words; map them to these canonical "
        "concepts and the matching tool, and answer in the user's language if you can):\n" + "\n".join(lines)
    )
