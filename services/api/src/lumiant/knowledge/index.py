"""A small hybrid retrieval index: BM25 keyword search, optionally fused with embedding similarity.

* Sources: the curated Markdown in `content/` (one chunk per `##` section) and the canonical catalog's dataset and
  field descriptions. Both are product text, not customer data.
* Keyword search always works (offline, no AI approval needed). When an approved provider supplies an embedder,
  dense similarity is fused with BM25 by reciprocal rank (RRF), so either signal can surface a chunk.
* Embeddings of the chunks are computed once per process and embedder, then cached in memory. A failing embedder
  is logged and the search falls back to keywords for that call.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lumiant.agent.terminology import normalize
from lumiant.canonical.catalog import CATALOG

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


def catalog_chunks() -> list[Chunk]:
    out = []
    for ds in CATALOG.values():
        fields = "; ".join(f"{f.name.replace('_', ' ')}: {f.description}" for f in ds.fields.values())
        out.append(Chunk(f"catalog#{ds.name}", "Data catalog", ds.name.replace("_", " "), f"{ds.description} {fields}"))
    return out


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
        self._vectors: dict[str, list[list[float]]] = {}

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
            # Field lists are long and mention every term once; curated explanations win a near tie.
            scores.append(s * CATALOG_WEIGHT if chunk.id.startswith("catalog#") else s)
        return scores

    # ---------------------------------------------------------------------------------- dense
    def _doc_vectors(self, embedder: Embedder, key: str) -> list[list[float]]:
        if key not in self._vectors:
            vectors: list[list[float]] = []
            texts = [c.body for c in self.chunks]
            for i in range(0, len(texts), 64):
                vectors += embedder(texts[i : i + 64], "RETRIEVAL_DOCUMENT")
            if len(vectors) != len(texts):
                raise ValueError("embedder returned the wrong number of vectors")
            self._vectors = {key: vectors}  # one embedder per process is the norm; never grow without bound
        return self._vectors[key]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        na = math.sqrt(sum(x * x for x in a)) or 1.0
        nb = math.sqrt(sum(y * y for y in b)) or 1.0
        return dot / (na * nb)

    # ---------------------------------------------------------------------------------- search
    def search(self, query: str, k: int = 4, embedder: Embedder | None = None, embed_key: str = "default") -> list[Hit]:
        """Top chunks for the query; `embed_key` names the embedding model so chunk vectors are reused."""
        keyword = self._bm25(query)
        ranked_kw = sorted(range(len(self.chunks)), key=lambda i: keyword[i], reverse=True)
        fused: dict[int, float] = {}
        for rank, i in enumerate(ranked_kw):
            if keyword[i] > 0:
                fused[i] = 1 / (RRF_K + rank + 1)
        if embedder is not None:
            try:
                docs = self._doc_vectors(embedder, embed_key)
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
    chunks: list[Chunk] = []
    for path in sorted(CONTENT_DIR.glob("*.md")):
        chunks += markdown_chunks(path)
    return KnowledgeIndex([*chunks, *catalog_chunks()])
