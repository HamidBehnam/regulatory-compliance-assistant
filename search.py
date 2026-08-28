"""Query an index. Online, per request, touches no source documents.

    uv run --env-file .env search.py "your question" [strategy] [top_k]

Embed the question with the model that embedded the corpus, score it against
every stored vector, return the closest chunks with their citations.
"""

import sys

from config import TOP_K
from embedding import embed
from similarity import normalize
from store import InMemoryStore, SearchResult, index_path

_BODY_PREVIEW_CHARS = 320


def search(
    store: InMemoryStore, query: str, *, top_k: int = TOP_K
) -> list[SearchResult]:
    """Return the chunks closest to ``query``, best first."""
    return store.search(normalize(embed([query])[0]), top_k=top_k)


def format_result(result: SearchResult, *, position: int) -> str:
    """Render one result for reading with your own eyes, which is the point."""
    chunk = result.chunk
    body = " ".join(chunk.body.split())
    if len(body) > _BODY_PREVIEW_CHARS:
        body = body[:_BODY_PREVIEW_CHARS] + "…"
    return (
        f"{position}. {chunk.citation}  "
        f"(score {result.score:.3f}, chunk {chunk.chunk_id})\n"
        f"   as of {chunk.snapshot_date} · {chunk.source_url}\n"
        f"   path: {chunk.heading_path or '(no heading in the embedded text)'}\n"
        f"   {body}\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('usage: search.py "your question" [strategy] [top_k]')
        return 1

    query = argv[1]
    strategy = argv[2] if len(argv) > 2 else "fixed"
    top_k = int(argv[3]) if len(argv) > 3 else TOP_K

    store = InMemoryStore.load(index_path(strategy))
    print(f'query: "{query}"   index: {strategy}   top {top_k}\n')
    for position, result in enumerate(search(store, query, top_k=top_k), start=1):
        print(format_result(result, position=position))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
