"""Lasting cache of embedding vectors for knowledge search (RAG v2).

Chunk text is embedded once and kept, so a cold start neither pays for nor waits on embedding the same text again.

* Key: sha256 of `model|dims|text`. Changing the text, the model or the vector size gives a new key, so a stale vector
  is never served for edited text.
* Lookup order: process memory, then the committed `content/vectors.json` (written by `lumiant-knowledge embed` for
  the static product chunks), then the app-DB table `knowledge_vector` (migration 0008). Vectors computed at run time
  go to memory and to that table. Every tier is optional, and a failing tier is logged and skipped: the worst case
  is an extra embed call, never a failed search.
* Only document vectors (task RETRIEVAL_DOCUMENT) are cached. A question is embedded fresh every time.
* Vectors are stored as base64 of little-endian float32 (about 4 KB for 768 dimensions), never as JSON floats.
  They are vectors of product and catalog text, never of customer figures.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import sys
import threading
from array import array
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, Session, mapped_column

from lumiant.audit.store import Base

log = logging.getLogger("lumiant.knowledge")

STATIC_PATH = Path(__file__).parent / "content" / "vectors.json"
FORMAT = 1
ENCODING = "base64-float32-le"
MEMORY_LIMIT = 4096  # about 12 MB at 768 dimensions
_DB_BATCH = 500

Vector = Sequence[float]


class KnowledgeVectorRow(Base):
    __tablename__ = "knowledge_vector"

    text_hash: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    model: Mapped[str] = mapped_column(sa.String(120))
    dims: Mapped[int] = mapped_column(sa.Integer())
    vector: Mapped[str] = mapped_column(sa.Text())
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))


# ------------------------------------------------------------------------------------------ keys and encoding
def vector_key(model: str, dims: int, text: str) -> str:
    return hashlib.sha256(f"{model}|{dims}|{text}".encode()).hexdigest()


def split_embed_key(embed_key: str) -> tuple[str, int]:
    """`gemini:gemini-embedding-001:768` -> (`gemini:gemini-embedding-001`, 768); a key without a size -> (key, 0)."""
    model, sep, dims = embed_key.rpartition(":")
    if sep and model and dims.isdigit():
        return model, int(dims)
    return embed_key, 0


def encode(vector: Vector) -> str:
    arr = array("f", vector)
    if sys.byteorder != "little":
        arr.byteswap()
    return base64.b64encode(arr.tobytes()).decode("ascii")


def decode(text: str) -> array[float]:
    raw = base64.b64decode(text, validate=True)
    if len(raw) % 4:
        raise ValueError("vector bytes are not whole float32 values")
    arr = array("f")
    arr.frombytes(raw)
    if sys.byteorder != "little":
        arr.byteswap()
    return arr


def _usable(text: str | None, dims: int) -> array[float] | None:
    """The decoded vector, or None when it is missing, unreadable or the wrong size (then it is embedded again)."""
    if not text:
        return None
    try:
        vec = decode(text)
    except ValueError:  # binascii.Error is a ValueError
        return None
    return vec if vec and (dims <= 0 or len(vec) == dims) else None


# ------------------------------------------------------------------------------------------ tiers
class VectorMemory:
    """Bounded LRU of vectors in this process (float32 arrays, not lists, to keep it small)."""

    def __init__(self, limit: int = MEMORY_LIMIT) -> None:
        self.limit = limit
        self._data: OrderedDict[str, array[float]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> array[float] | None:
        with self._lock:
            vec = self._data.get(key)
            if vec is not None:
                self._data.move_to_end(key)
            return vec

    def put(self, key: str, vec: array[float]) -> None:
        with self._lock:
            self._data[key] = vec
            self._data.move_to_end(key)
            while len(self._data) > self.limit:
                self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


_MEMORY = VectorMemory()


@lru_cache(maxsize=4)
def _static_vectors(path: str) -> Mapping[str, str]:
    """key -> encoded vector from a committed vectors file; empty when the file is absent or unreadable."""
    p = Path(path)
    if not p.is_file():
        return {}
    try:
        doc: Any = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or doc.get("format") != FORMAT or doc.get("encoding") != ENCODING:
            raise ValueError("unknown vectors file format")
        vectors = doc.get("vectors")
        if not isinstance(vectors, dict):
            raise ValueError("vectors file has no vectors")
        return {k: v for k, v in vectors.items() if isinstance(k, str) and isinstance(v, str)}
    except (OSError, ValueError) as exc:
        log.warning("knowledge_vectors_file_unreadable", extra={"error_type": type(exc).__name__})
        return {}


class VectorCache:
    """Memory, then the committed file, then the app DB. Pass `engine=None` or `static_path=None` to skip a tier."""

    def __init__(
        self,
        engine: sa.Engine | None = None,
        static_path: Path | None = STATIC_PATH,
        memory: VectorMemory | None = None,
    ) -> None:
        self.engine = engine
        self.static_path = static_path
        self.memory = memory if memory is not None else _MEMORY

    def get_many(self, keys: Sequence[str], dims: int) -> dict[str, Vector]:
        found: dict[str, Vector] = {}
        missing: list[str] = []
        for key in dict.fromkeys(keys):
            vec = self.memory.get(key)
            if vec is not None and (dims <= 0 or len(vec) == dims):
                found[key] = vec
            else:
                missing.append(key)
        if missing and self.static_path is not None:
            static = _static_vectors(str(self.static_path))
            still: list[str] = []
            for key in missing:
                vec = _usable(static.get(key), dims)
                if vec is None:
                    still.append(key)
                else:
                    found[key] = vec
                    self.memory.put(key, vec)
            missing = still
        if missing and self.engine is not None:
            for key, vec in self._db_get(missing, dims).items():
                found[key] = vec
                self.memory.put(key, vec)
        return found

    def put_many(self, vectors: Mapping[str, Vector], model: str, dims: int) -> None:
        if not vectors:
            return
        packed = {key: array("f", vec) for key, vec in vectors.items()}
        for key, vec in packed.items():
            self.memory.put(key, vec)
        if self.engine is not None:
            self._db_put(packed, model, dims)

    # ---------------------------------------------------------------------------------- app DB
    def _db_get(self, keys: list[str], dims: int) -> dict[str, array[float]]:
        assert self.engine is not None
        out: dict[str, array[float]] = {}
        row = KnowledgeVectorRow
        try:
            with Session(self.engine) as session:
                for i in range(0, len(keys), _DB_BATCH):
                    stmt = sa.select(row.text_hash, row.vector).where(row.text_hash.in_(keys[i : i + _DB_BATCH]))
                    for text_hash, text in session.execute(stmt):
                        vec = _usable(text, dims)
                        if vec is not None:
                            out[text_hash] = vec
        except sa.exc.SQLAlchemyError as exc:
            log.warning("knowledge_vector_store_unavailable", extra={"error_type": type(exc).__name__})
            return {}
        return out

    def _db_put(self, vectors: dict[str, array[float]], model: str, dims: int) -> None:
        assert self.engine is not None
        row = KnowledgeVectorRow
        keys = list(vectors)
        now = datetime.now(UTC)
        try:
            with Session(self.engine) as session, session.begin():
                existing: set[str] = set()
                for i in range(0, len(keys), _DB_BATCH):
                    batch = keys[i : i + _DB_BATCH]
                    existing.update(session.scalars(sa.select(row.text_hash).where(row.text_hash.in_(batch))))
                session.add_all(
                    row(text_hash=k, model=model[:120], dims=dims or len(v), vector=encode(v), created_at=now)
                    for k, v in vectors.items()
                    if k not in existing
                )
        except sa.exc.IntegrityError:
            pass  # another instance stored the same vectors first; theirs are identical
        except sa.exc.SQLAlchemyError as exc:
            log.warning("knowledge_vector_store_unavailable", extra={"error_type": type(exc).__name__})


def vector_cache(engine: sa.Engine | None = None) -> VectorCache:
    """The process-wide cache (shared memory and committed file), backed by the app DB when an engine is given."""
    return VectorCache(engine)


def write_static(path: Path, vectors: Mapping[str, Vector], model: str, dims: int) -> None:
    """Write a committed vectors file (used by `lumiant-knowledge embed`)."""
    doc = {
        "format": FORMAT,
        "encoding": ENCODING,
        "model": model,
        "dims": dims,
        "count": len(vectors),
        "vectors": {k: encode(vectors[k]) for k in sorted(vectors)},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=0) + "\n", encoding="utf-8")
    _static_vectors.cache_clear()
