"""Score an index against the hand-labelled questions.

    uv run --env-file .env evaluate.py [fixed|structural]

Reading results by eye is where the understanding comes from, but a retrieval
failure here looks like five plausible passages of regulatory text, one of
which is about the wrong kind of financial institution. Two numbers catch what
reading does not:

**recall@5** — did any acceptable section appear in the top five?

**distinct sections in the top 5 chunks** — how much of the raw ranking is
separate sections rather than fragments of one section shouting over the
others. Measured on `rank_chunks`, before `search` collapses to one chunk per
section: measured after, it would be 5.0 for every question by construction.
"""

import sys

from config import TOP_K
from questions import QUESTIONS
from search import embed_query
from store import InMemoryStore, index_path


def evaluate(strategy: str) -> None:
    """Run every question against ``strategy``'s index and print the scores."""
    store = InMemoryStore.load(index_path(strategy))
    print(
        f"index: {strategy}  ({store.header.chunk_count} chunks from "
        f"{store.header.section_count} sections, {store.header.chunker_params})\n"
    )

    hits = 0
    distinct_total = 0
    for question, acceptable in QUESTIONS:
        # One embedding, both rankings: the collapsed list is what a user sees,
        # the raw one is what the diversity number has to be measured on.
        vector = embed_query(question)
        retrieved = [r.chunk.section_number for r in store.search(vector, top_k=TOP_K)]
        ranked = [
            r.chunk.section_number for r in store.rank_chunks(vector, top_k=TOP_K)
        ]
        hit = bool(acceptable.intersection(retrieved))
        hits += hit
        distinct_total += len(set(ranked))

        print(f"{'HIT ' if hit else 'MISS'} {question}")
        print(f"     wanted any of: {', '.join(sorted(acceptable))}")
        print(f"     got:           {', '.join(retrieved)}")
        print(f"     raw chunks:    {', '.join(ranked)}\n")

    print(f"recall@{TOP_K}: {hits}/{len(QUESTIONS)}")
    print(
        f"distinct sections in the top {TOP_K} chunks: "
        f"{distinct_total / len(QUESTIONS):.1f} of {TOP_K}"
    )


def main(argv: list[str]) -> int:
    evaluate(argv[1] if len(argv) > 1 else "fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
