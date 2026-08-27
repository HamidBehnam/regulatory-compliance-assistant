"""Build a searchable index. Offline, re-runnable, slow-is-fine.

    uv run --env-file .env index.py [fixed|structural]

This is the whole indexing pipeline: fetch, parse, chunk, embed, store. It
runs from scratch every time and overwrites its output, because during a week
of learning what your chunker actually does to a document you will run it many
times, and an indexer you have to reason about the state of is an indexer you
will avoid re-running.

Source documents are cached on disk after the first run, so re-chunking costs
nothing but the embedding calls — and those are cents.
"""

import sys

from chunking import CHUNKERS
from config import (
    EMBEDDING_DIMENSIONS,
    FIXED_CHUNK_CHARS,
    FIXED_CHUNK_OVERLAP,
    MAX_CHUNK_CHARS,
    SNAPSHOT_DATE,
)
from ecfr import load_sections
from embedding import Embedder, OpenAIEmbedder
from models import EmbeddedChunk
from similarity import normalize
from store import IndexHeader, InMemoryStore, index_path

#: Recorded in the header so an index says how it was chunked, not just that
#: it was. A recall number is only comparable against another run if you can
#: see what changed between them.
_CHUNKER_PARAMS: dict[str, dict[str, int]] = {
    "fixed": {"size": FIXED_CHUNK_CHARS, "overlap": FIXED_CHUNK_OVERLAP},
    "structural": {"max_chars": MAX_CHUNK_CHARS},
}


def build(strategy: str, *, embedder: Embedder | None = None) -> InMemoryStore:
    """Fetch, chunk, embed, and store the corpus under one chunking strategy."""
    embedder = embedder or OpenAIEmbedder()

    sections = load_sections()
    print(f"loaded {len(sections)} sections as of {SNAPSHOT_DATE}")

    chunks = CHUNKERS[strategy](sections)
    print(f"{strategy}: {len(chunks)} chunks")

    vectors = embedder.embed([chunk.embed_text for chunk in chunks])
    print(f"embedded {len(vectors)} chunks with {embedder.model}")

    store = InMemoryStore(
        header=IndexHeader(
            snapshot_date=SNAPSHOT_DATE,
            embedding_model=embedder.model,
            dimensions=EMBEDDING_DIMENSIONS,
            chunker=strategy,
            chunker_params=_CHUNKER_PARAMS[strategy],
            chunk_count=len(chunks),
            section_count=len(sections),
        ),
        chunks=[
            EmbeddedChunk(chunk=chunk, vector=normalize(vector))
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )

    path = index_path(strategy)
    store.save(path)
    print(f"wrote {path}")
    return store


def main(argv: list[str]) -> int:
    strategy = argv[1] if len(argv) > 1 else "fixed"
    if strategy not in CHUNKERS:
        print(f"unknown strategy {strategy!r}; try one of {sorted(CHUNKERS)}")
        return 1
    build(strategy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
