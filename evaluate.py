"""Score an index against the hand-labelled questions.

    uv run --env-file .env evaluate.py [fixed|structural]

Reading results by eye is where the understanding comes from, and it is not
optional — but it does not catch everything. A retrieval failure in this corpus
looks like five plausible passages of regulatory text, one of which is about
the wrong kind of financial institution. You read it, it reads correctly, and
you move on. A number does not.

Two are reported:

**recall@5** — did any acceptable section appear in the top five? This is the
one that answers "did the chunking change help", and it is the number that
belongs in the README.

**distinct sections in top 5** — how much of the result list is separate
sections rather than fragments of the same one. It measures the failure recall
alone would hide: a long section split into many pieces filling the whole list
with itself, which looks like a confident answer and is actually one section
shouting over the others.
"""

import sys

from config import DEFAULT_TOP_K, EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from embedding import Embedder, OpenAIEmbedder
from questions import QUESTIONS
from search import search
from store import InMemoryStore, index_path


def evaluate(
    strategy: str, *, top_k: int = DEFAULT_TOP_K, embedder: Embedder | None = None
) -> tuple[int, float]:
    """Run every question against ``strategy``'s index and report.

    Args:
        strategy: Which index to score.
        top_k: Cutoff for recall.
        embedder: Defaults to the configured provider.

    Returns:
        (hits out of len(QUESTIONS), mean distinct sections per result list).
    """
    embedder = embedder or OpenAIEmbedder()
    store = InMemoryStore.load(
        index_path(strategy),
        embedding_model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
    )

    print(
        f"index: {strategy}  ({store.header.chunk_count} chunks from "
        f"{store.header.section_count} sections, {store.header.chunker_params})\n"
    )

    hits = 0
    distinct_total = 0
    for question, acceptable in QUESTIONS:
        results = search(
            question, strategy=strategy, top_k=top_k, embedder=embedder, store=store
        )
        retrieved = [r.chunk.section_number for r in results]
        hit = bool(acceptable.intersection(retrieved))
        hits += hit
        distinct_total += len(set(retrieved))

        print(f"{'HIT ' if hit else 'MISS'} {question}")
        print(f"     wanted any of: {', '.join(sorted(acceptable))}")
        print(f"     got:           {', '.join(retrieved)}\n")

    distinct = distinct_total / len(QUESTIONS)
    print(f"recall@{top_k}: {hits}/{len(QUESTIONS)}")
    print(f"distinct sections in top {top_k}: {distinct:.1f}")
    return hits, distinct


def main(argv: list[str]) -> int:
    strategy = argv[1] if len(argv) > 1 else "fixed"
    evaluate(strategy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
