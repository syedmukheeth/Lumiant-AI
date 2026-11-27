"""Knowledge maintenance. Embed the static product chunks once and commit the result, so a cold start does not
re-embed them:

    uv run lumiant-knowledge embed

Needs LUMIANT_GEMINI_API_KEY (environment or services/api/.env) and refuses without it. It sends Lumiant's own product
text and catalog descriptions to the embedding model, never customer data, and writes
`src/lumiant/knowledge/content/vectors.json` (base64 float32 vectors keyed by sha256 of model|dims|text). Run it again
after editing the Markdown in `content/` or the catalog; vectors for changed text are simply new keys.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from lumiant.core.config import Settings, get_settings
from lumiant.knowledge.index import EMBED_BATCH, Embedder, product_index
from lumiant.knowledge.vectors import STATIC_PATH, Vector, split_embed_key, vector_key, write_static

NO_KEY = (
    "lumiant-knowledge embed needs LUMIANT_GEMINI_API_KEY (environment or services/api/.env) to call the embedding "
    "model. Nothing was written."
)


def embed_static(embedder: Embedder, embed_key: str, out: Path = STATIC_PATH) -> int:
    """Embed every static product chunk (Markdown sections and the full catalog) and write the vectors file."""
    model, dims = split_embed_key(embed_key)
    texts = list(dict.fromkeys(c.body for c in product_index().chunks))
    vectors: dict[str, Vector] = {}
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        result = embedder(batch, "RETRIEVAL_DOCUMENT")
        if len(result) != len(batch):
            raise ValueError("embedder returned the wrong number of vectors")
        for text, vec in zip(batch, result, strict=True):
            if dims and len(vec) != dims:
                raise ValueError(f"embedder returned {len(vec)} dimensions, expected {dims}")
            vectors[vector_key(model, dims, text)] = vec
    write_static(out, vectors, model, dims)
    return len(vectors)


def run_embed(settings: Settings | None = None, out: Path = STATIC_PATH) -> int:
    cfg = settings or get_settings()
    key = cfg.gemini_api_key.get_secret_value().strip() if cfg.gemini_api_key else ""
    if not key:
        print(NO_KEY, file=sys.stderr)
        return 2
    from lumiant.agent.providers import GeminiProvider

    provider = GeminiProvider(key, cfg.gemini_model)
    count = embed_static(provider.embed, provider.embed_key, out)
    print(f"Wrote {count} vectors ({provider.embed_key}) to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="lumiant-knowledge", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    embed = sub.add_parser("embed", help="embed the static product chunks into content/vectors.json")
    embed.add_argument("--out", type=Path, default=STATIC_PATH, help="where to write the vectors file")
    args = parser.parse_args(argv)
    return run_embed(out=args.out)


if __name__ == "__main__":
    sys.exit(main())
