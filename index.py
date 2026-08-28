"""Build a searchable index: fetch, parse, chunk, embed, store.

    uv run --env-file .env index.py [fixed|structural]

Runs from scratch and overwrites its output every time. Source documents are
cached on disk after the first run, so re-chunking costs only the embedding
calls, and those are cents.
"""

import sys

from chunking import CHUNKER_PARAMS, CHUNKERS
from config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, SNAPSHOT_DATE
from ecfr import load_sections
from embedding import embed
from models import EmbeddedChunk
from similarity import normalize
from store import IndexHeader, InMemoryStore, index_path


def build(strategy: str) -> None:
    """Index the corpus under one chunking strategy."""
    sections = load_sections()
    print(f"loaded {len(sections)} sections as of {SNAPSHOT_DATE}")

    chunks = CHUNKERS[strategy](sections)
    print(f"{strategy}: {len(chunks)} chunks")

    vectors = embed([chunk.embed_text for chunk in chunks])
    print(f"embedded {len(vectors)} chunks with {EMBEDDING_MODEL}")

    store = InMemoryStore(
        IndexHeader(
            snapshot_date=SNAPSHOT_DATE,
            embedding_model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            chunker=strategy,
            chunker_params=CHUNKER_PARAMS[strategy],
            chunk_count=len(chunks),
            section_count=len(sections),
        ),
        [
            EmbeddedChunk(chunk=chunk, vector=normalize(vector))
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )

    path = index_path(strategy)
    store.save(path)
    print(f"wrote {path}")


def main(argv: list[str]) -> int:
    strategy = argv[1] if len(argv) > 1 else "fixed"
    if strategy not in CHUNKERS:
        print(f"unknown strategy {strategy!r}; try one of {sorted(CHUNKERS)}")
        return 1
    build(strategy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
