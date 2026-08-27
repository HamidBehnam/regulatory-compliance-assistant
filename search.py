"""Query the index. Online, per request, touches no source documents.

    uv run --env-file .env search.py "your question" [strategy] [top_k]

The query pipeline is deliberately small: embed the question with the same
model that embedded the corpus, score it against every stored vector, return
the closest chunks with their citations. Everything expensive happened offline.
"""

import sys

from config import DEFAULT_TOP_K, EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from embedding import Embedder, OpenAIEmbedder
from similarity import normalize
from store import InMemoryStore, SearchResult, index_path


def search(
    query: str,
    *,
    strategy: str = "fixed",
    top_k: int = DEFAULT_TOP_K,
    embedder: Embedder | None = None,
    store: InMemoryStore | None = None,
) -> list[SearchResult]:
    """Return the chunks closest to ``query``.

    Args:
        query: A natural-language question.
        strategy: Which index to read.
        top_k: How many results to return.
        embedder: Defaults to the configured provider. Must be the same model
            that built the index; the store checks and refuses otherwise.
        store: A preloaded store, so a caller running many queries does not
            re-read the index for each one.

    Returns:
        Up to ``top_k`` results, best first.
    """
    embedder = embedder or OpenAIEmbedder()
    store = store or InMemoryStore.load(
        index_path(strategy),
        embedding_model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    query_vector = normalize(embedder.embed([query])[0])
    return store.search(query_vector, top_k=top_k)


def format_result(result: SearchResult, *, position: int, body_chars: int = 320) -> str:
    """Render one result for reading with your own eyes, which is the point."""
    chunk = result.chunk
    body = " ".join(chunk.body.split())
    if len(body) > body_chars:
        body = body[:body_chars] + "…"
    heading = chunk.heading_path or "(no heading in the embedded text)"
    return (
        f"{position}. {chunk.citation}  (score {result.score:.3f}, chunk {chunk.chunk_id})\n"
        f"   as of {chunk.snapshot_date} · {chunk.source_url}\n"
        f"   path: {heading}\n"
        f"   {body}\n"
    )


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print('usage: search.py "your question" [strategy] [top_k]')
        return 1

    query = argv[1]
    strategy = argv[2] if len(argv) > 2 else "fixed"
    top_k = int(argv[3]) if len(argv) > 3 else DEFAULT_TOP_K

    results = search(query, strategy=strategy, top_k=top_k)
    print(f'query: "{query}"   index: {strategy}   top {top_k}\n')
    for position, result in enumerate(results, start=1):
        print(format_result(result, position=position))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
