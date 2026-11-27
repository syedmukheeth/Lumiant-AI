"""A small hybrid retrieval index: BM25 keyword search, optionally fused with embedding similarity.

* Sources: the curated Markdown in `content/` (one chunk per `##` section) and the canonical catalog's dataset and
  field descriptions. Both are product text, not customer data.
* `product_index()` holds every catalog dataset and field. `tenant_index(tenant, can_cost)` is what the Analyst
  searches (RAG v2): the product text plus only the datasets and fields that organisation maps (cost-sensitive fields
  left out for roles without cost access), where its missing data would come from (`source_hints`), and one chunk
  naming the canonical datasets it does not map, so "can you show our profit?" finds a plain answer.
* Keyword search always works (offline, no AI approval needed). When an approved provider supplies an embedder,
  dense similarity is fused with BM25 by reciprocal rank (RRF), so either signal can surface a chunk.
* Chunk vectors come from the lasting cache in `vectors.py` (memory, committed file, app DB); only missing ones are
  embedded. A failing embedder is logged and the search falls back to keywords for that call.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
from collections import Counter, OrderedDict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from lumiant.agent.terminology import normalize
from lumiant.canonical.catalog import CATALOG, DatasetDef, FieldDef, Sensitivity
from lumiant.knowledge.vectors import Vector, VectorCache, split_embed_key, vector_cache, vector_key

if TYPE_CHECKING:
    from lumiant.tenancy.models import DatasetMapping, TenantConfig

log = logging.getLogger("lumiant.knowledge")

# texts, task ("RETRIEVAL_DOCUMENT" | "RETRIEVAL_QUERY") -> one vector per text
Embedder = Callable[[list[str], str], list[list[float]]]

CONTENT_DIR = Path(__file__).parent / "content"
_TOKEN = re.compile(r"[a-z0-9؀-ۿ]+")
_STOP = frozenset(
    {
        *("a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "has", "have"),
        *("how", "i", "in", "is", "it", "its", "me", "of", "on", "or", "our", "show", "that", "the", "their"),
        *("there", "this", "to", "was", "we", "what", "when", "where", "which", "who", "why", "will", "with"),
        *("you", "your"),
    }
)
RRF_K = 60
CATALOG_WEIGHT = 0.8
MIN_KEYWORD_SCORE = 1.0
EMBED_BATCH = 64
TENANT_CACHE_SIZE = 32
CATALOG_SOURCE = "Data catalog"
TENANT_SOURCE = "This organisation's data"
_LIST_CHUNKS = ("catalog#", "tenant#source_hints")  # weighted by CATALOG_WEIGHT in keyword scoring


@dataclass(frozen=True)
class Chunk:
    id: str
    source: str  # document title
    heading: str
    text: str

    @property
    def body(self) -> str:
        return f"{self.heading}. {self.text}"


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    keyword: float


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(normalize(text)) if t not in _STOP and len(t) > 1]


def markdown_chunks(path: Path) -> list[Chunk]:
    """One chunk per `##` section; the `#` title names the source."""
    title, heading = path.stem.replace("_", " ").capitalize(), ""
    lines: list[str] = []
    out: list[Chunk] = []

    def flush() -> None:
        body = " ".join(" ".join(lines).split())
        if heading and body:
            out.append(Chunk(f"{path.stem}#{len(out)}", title, heading, body))

    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            flush()
            heading, lines = line[3:].strip(), []
        elif heading:
            lines.append(line.strip())
    flush()
    return out


def _words(name: str) -> str:
    return name.replace("_", " ")


def _catalog_chunk(ds: DatasetDef, entries: Iterable[str]) -> Chunk:
    return Chunk(f"catalog#{ds.name}", CATALOG_SOURCE, _words(ds.name), f"{ds.description} {'; '.join(entries)}")


def catalog_chunks() -> list[Chunk]:
    return [
        _catalog_chunk(ds, (f"{_words(f.name)}: {f.description}" for f in ds.fields.values()))
        for ds in CATALOG.values()
    ]


@lru_cache(maxsize=1)
def product_chunks() -> tuple[Chunk, ...]:
    """The curated Markdown sections: static product text, the same for every organisation."""
    chunks: list[Chunk] = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        chunks += markdown_chunks(path)
    return tuple(chunks)


# ------------------------------------------------------------------------------------------ per organisation
def visible_fields(ds: DatasetDef, ds_map: DatasetMapping, can_cost: bool) -> list[FieldDef]:
    """The catalog fields this mapping serves (a computed field when all its operands are mapped), in catalog order.

    Without cost access, cost-sensitive fields are left out, and so is a currency field that only qualifies them
    (the currency of a price the role cannot see)."""
    mapped = set(ds_map.fields)
    fields = [
        f
        for f in ds.fields.values()
        if (all(op in mapped for op in f.product_of) if f.product_of is not None else f.name in mapped)
    ]
    if can_cost:
        return fields
    cost_currency = {f.currency_field for f in ds.fields.values() if f.sensitivity is Sensitivity.COST}
    plain_currency = {f.currency_field for f in ds.fields.values() if f.sensitivity is not Sensitivity.COST}
    return [
        f
        for f in fields
        if f.sensitivity is not Sensitivity.COST and (f.name not in cost_currency or f.name in plain_currency)
    ]


def tenant_catalog_chunks(tenant: TenantConfig, can_cost: bool) -> list[Chunk]:
    out = []
    for ds in CATALOG.values():
        ds_map = tenant.datasets.get(ds.name)
        if ds_map is None:
            continue
        entries = [f"{_words(f.name)}: {f.description}" for f in visible_fields(ds, ds_map, can_cost)]
        # Customer attributes carry no cost flag; the query engine serves them to every reader of the dataset.
        entries += [f"{_words(name)}: {a.description or 'customer attribute'}" for name, a in ds_map.attributes.items()]
        out.append(_catalog_chunk(ds, entries))
    return out


def source_hints_chunk(tenant: TenantConfig, can_cost: bool) -> Chunk | None:
    entries = []
    for key, hint in tenant.source_hints.items():
        ds_name, _, field_name = key.partition(".")
        ds = CATALOG.get(ds_name)
        if ds is None:
            continue
        if field_name:
            fdef = ds.fields.get(field_name)
            if fdef is None or (not can_cost and fdef.sensitivity is Sensitivity.COST):
                continue
            entries.append(f"{_words(field_name)} of {_words(ds_name)}: {hint}")
        else:
            entries.append(f"{_words(ds_name)}: {hint}")
    if not entries:
        return None
    text = "Data that is not connected yet for this organisation would come from these sources. " + "; ".join(entries)
    return Chunk("tenant#source_hints", TENANT_SOURCE, "Where missing data would come from", text + ".")


# What a canonical dataset would add, in plain words, when it is NOT mapped: (any role, roles with cost access).
_NOT_MAPPED: dict[str, tuple[str, str | None]] = {
    "item": ("No item master, so item descriptions, groups, stages and units are unknown.", None),
    "warehouse": ("No warehouse or plant list.", None),
    "storage_location": ("No storage locations inside warehouses.", None),
    "stock_balance": ("No stock on hand.", "No stock on hand and no inventory value."),
    "item_warehouse": (
        "No plant planning settings such as planning type, lead times and lot sizes.",
        "No plant planning settings such as planning type, lead times and lot sizes, and no plant valuation prices.",
    ),
    "reorder_policy": (
        "No reorder levels or maximum stock, so items below reorder level or above maximum cannot be found.",
        None,
    ),
    "lot": (
        "No lots or batches with expiry dates, so expiring and expired stock cannot be shown.",
        "No lots or batches with expiry dates or lot costs, so expiring and expired stock cannot be shown.",
    ),
    "inventory_transaction": (
        "No stock movement history (receipts, issues, transfers), so dormant or idle stock, usage, turns, days of "
        "cover and the value trend cannot be worked out.",
        "No stock movement history (receipts, issues, transfers) or movement costs, so dormant or idle stock, usage, "
        "turns, days of cover, the value trend and costing methods cannot be worked out.",
    ),
    "purchase_record": (
        "No purchase orders, so open supply, deliveries and actual supplier lead times are unknown.",
        "No purchase orders or purchase prices, so open supply, deliveries, actual supplier lead times and the latest "
        "price are unknown.",
    ),
    "supplier": ("No supplier master.", None),
    "bom_component": ("No bills of materials, so BOM explosion and material planning cannot run.", None),
    "item_alternate": ("No approved alternate items.", None),
    "supplier_item": (
        "No supplier item records such as minimum order quantities and supplier lead times.",
        "No supplier quotations: no quoted prices, minimum order quantities or supplier lead times.",
    ),
    "customer_order_line": (
        "No customer orders or sales demand, so order fulfilment cannot be checked.",
        "No customer orders, sales demand, selling prices or margins, so order fulfilment cannot be checked.",
    ),
    "department": ("No departments that own warehouses.", None),
}
NO_SALES_HISTORY = (
    "Lumiant's data model holds no invoiced sales history, revenue or profit for any organisation: a profit or margin "
    "analysis needs sales or finance data, which is not connected."
)


def not_mapped_chunk(tenant: TenantConfig, can_cost: bool) -> Chunk:
    sentences = []
    for name in CATALOG:
        if name in tenant.datasets:
            continue
        plain, with_cost = _NOT_MAPPED.get(name, (f"No {_words(name)}.", None))
        sentences.append(with_cost if can_cost and with_cost else plain)
    lead = (
        "This organisation's connected data does not include the following. " + " ".join(sentences)
        if sentences
        else "Every dataset in Lumiant's data model is connected for this organisation."
    )
    return Chunk("tenant#not_mapped", TENANT_SOURCE, "Not in this organisation's data", f"{lead} {NO_SALES_HISTORY}")


def tenant_chunks(tenant: TenantConfig, can_cost: bool) -> list[Chunk]:
    hints = source_hints_chunk(tenant, can_cost)
    return [
        *product_chunks(),
        *tenant_catalog_chunks(tenant, can_cost),
        *([hints] if hints is not None else []),
        not_mapped_chunk(tenant, can_cost),
    ]


class KnowledgeIndex:
    def __init__(self, chunks: Iterable[Chunk]) -> None:
        self.chunks = list(chunks)
        self._docs = [Counter(tokens(c.body + " " + c.source)) for c in self.chunks]
        self._len = [sum(d.values()) for d in self._docs]
        self._avg = (sum(self._len) / len(self._len)) if self._len else 0.0
        df: Counter[str] = Counter()
        for d in self._docs:
            df.update(d.keys())
        n = len(self.chunks)
        self._idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self._vectors: dict[str, list[Vector]] = {}

    # ---------------------------------------------------------------------------------- keyword
    def _bm25(self, query: str, k1: float = 1.4, b: float = 0.75) -> list[float]:
        q = tokens(query)
        scores = []
        for chunk, doc, length in zip(self.chunks, self._docs, self._len, strict=True):
            s = 0.0
            for t in q:
                tf = doc.get(t, 0)
                if tf:
                    s += self._idf[t] * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / (self._avg or 1)))
            # Field and source lists are long and mention every term once; curated explanations win a near tie.
            scores.append(s * CATALOG_WEIGHT if chunk.id.startswith(_LIST_CHUNKS) else s)
        return scores

    # ---------------------------------------------------------------------------------- dense
    def _doc_vectors(self, embedder: Embedder, key: str, cache: VectorCache | None) -> list[Vector]:
        """One vector per chunk: from the lasting cache where present, embedding only the chunks it lacks."""
        if key not in self._vectors:
            store = cache if cache is not None else vector_cache()
            model, dims = split_embed_key(key)
            texts = [c.body for c in self.chunks]
            keys = [vector_key(model, dims, t) for t in texts]
            found = store.get_many(keys, dims)
            text_of = dict(zip(keys, texts, strict=True))
            todo = [k for k in text_of if k not in found]
            fresh: dict[str, Vector] = {}
            for i in range(0, len(todo), EMBED_BATCH):
                batch = todo[i : i + EMBED_BATCH]
                out = embedder([text_of[k] for k in batch], "RETRIEVAL_DOCUMENT")
                if len(out) != len(batch):
                    raise ValueError("embedder returned the wrong number of vectors")
                fresh.update(zip(batch, out, strict=True))
            store.put_many(fresh, model, dims)
            found.update(fresh)
            self._vectors = {key: [found[k] for k in keys]}  # one embedder per process is the norm; never grow
        return self._vectors[key]

    @staticmethod
    def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    # ---------------------------------------------------------------------------------- search
    def search(
        self,
        query: str,
        k: int = 4,
        embedder: Embedder | None = None,
        embed_key: str = "default",
        vectors: VectorCache | None = None,
    ) -> list[Hit]:
        """Top chunks for the query. `embed_key` names the embedding model and size (`provider:model:dims`) so chunk
        vectors are reused; `vectors` is the lasting cache (memory and the committed file when not given)."""
        keyword = self._bm25(query)
        ranked_kw = sorted(range(len(self.chunks)), key=lambda i: keyword[i], reverse=True)
        fused: dict[int, float] = {}
        for rank, i in enumerate(ranked_kw):
            if keyword[i] > 0:
                fused[i] = 1 / (RRF_K + rank + 1)
        if embedder is not None:
            try:
                docs = self._doc_vectors(embedder, embed_key, vectors)
                qv = embedder([query], "RETRIEVAL_QUERY")[0]
                dense = [self._cosine(qv, d) for d in docs]
                for rank, i in enumerate(sorted(range(len(docs)), key=lambda i: dense[i], reverse=True)[: k * 3]):
                    fused[i] = fused.get(i, 0.0) + 1 / (RRF_K + rank + 1)
            except Exception as exc:  # the keyword result still stands
                log.warning("knowledge_embedding_failed", extra={"error_type": type(exc).__name__})
        best = sorted(fused, key=lambda i: fused[i], reverse=True)[:k]
        return [Hit(self.chunks[i], fused[i], keyword[i]) for i in best]

    def best_keyword(self, query: str) -> Hit | None:
        """The single best keyword hit if it is a confident match (used by the offline matcher)."""
        scores = self._bm25(query)
        if not scores:
            return None
        i = max(range(len(scores)), key=lambda j: scores[j])
        return Hit(self.chunks[i], scores[i], scores[i]) if scores[i] >= MIN_KEYWORD_SCORE else None


@lru_cache(maxsize=1)
def product_index() -> KnowledgeIndex:
    """Product text and the whole catalog, the same for everyone (offline matching, tests, the embed command)."""
    return KnowledgeIndex([*product_chunks(), *catalog_chunks()])


def mapping_fingerprint(tenant: TenantConfig) -> str:
    """Changes whenever the mapping or the source hints change, so an edited configuration gets a fresh index."""
    doc = {
        "datasets": {name: m.model_dump(mode="json") for name, m in tenant.datasets.items()},
        "source_hints": dict(tenant.source_hints),
    }
    return hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest()


_tenant_indexes: OrderedDict[tuple[str, str, bool], KnowledgeIndex] = OrderedDict()
_tenant_lock = threading.Lock()


def tenant_index(tenant: TenantConfig, can_cost: bool) -> KnowledgeIndex:
    """The index the Analyst searches for one organisation and cost permission (an LRU of TENANT_CACHE_SIZE)."""
    key = (tenant.id, mapping_fingerprint(tenant), can_cost)
    with _tenant_lock:
        index = _tenant_indexes.get(key)
        if index is not None:
            _tenant_indexes.move_to_end(key)
            return index
    built = KnowledgeIndex(tenant_chunks(tenant, can_cost))  # outside the lock: building tokenises every chunk
    with _tenant_lock:
        index = _tenant_indexes.setdefault(key, built)
        _tenant_indexes.move_to_end(key)
        while len(_tenant_indexes) > TENANT_CACHE_SIZE:
            _tenant_indexes.popitem(last=False)
    return index


def clear_tenant_indexes() -> None:
    with _tenant_lock:
        _tenant_indexes.clear()
