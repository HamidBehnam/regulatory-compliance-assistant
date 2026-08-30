"""Score an index against the hand-labelled questions.

    uv run --env-file .env evaluate.py [fixed|structural]

Reading results by eye is where the understanding comes from, but a retrieval
failure here looks like five plausible passages of regulatory text, one of
which is about the wrong kind of financial institution. Four numbers catch what
reading does not:

**recall@5** — did any acceptable section appear in the top five? Saturated on
this question set: both strategies score 10/10, so it cannot discriminate
between them and the three numbers below are what carry the comparison.

**recall@1** — was the first result acceptable? The top of the list is what a
hurried reader acts on, and unlike recall@5 it still has room to move.

**MRR** — mean reciprocal rank of the first acceptable section, 0 where none
appears in the top five. Rank-sensitive where recall@5 is a step function, so a
correct answer sliding from first to third is visible here and nowhere else.

**distinct sections in the top 5 chunks** — how much of the raw ranking is
separate sections rather than fragments of one section shouting over the
others. Measured on `rank_chunks`, before `search` collapses to one chunk per
section: measured after, it would be 5.0 for every question by construction.

recall@1 and MRR are both measured on the collapsed list `search` returns,
which is what a user sees. At rank 1 the two lists agree by construction — the
best-scoring chunk overall heads both — so recall@1 is not an artefact of the
collapse; MRR below rank 1 is.
"""

import sys

from config import TOP_K
from questions import QUESTIONS
from search import embed_query
from store import InMemoryStore, index_path


def first_hit_rank(retrieved: list[str], acceptable: frozenset[str]) -> int | None:
    """1-based rank of the first acceptable section, or None if none of them
    appear. Ranking a section rather than a chunk: the expectation sets are
    written in citations, which is the unit a compliance officer checks."""
    for rank, section_number in enumerate(retrieved, start=1):
        if section_number in acceptable:
            return rank
    return None


def evaluate(strategy: str) -> None:
    """Run every question against ``strategy``'s index and print the scores."""
    store = InMemoryStore.load(index_path(strategy))
    print(
        f"index: {strategy}  ({store.header.chunk_count} chunks from "
        f"{store.header.section_count} sections, {store.header.chunker_params})\n"
    )

    hits = 0
    top_hits = 0
    reciprocal_total = 0.0
    distinct_total = 0
    for question, acceptable in QUESTIONS:
        # One embedding, both rankings: the collapsed list is what a user sees,
        # the raw one is what the diversity number has to be measured on.
        vector = embed_query(question)
        retrieved = [r.chunk.section_number for r in store.search(vector, top_k=TOP_K)]
        ranked = [
            r.chunk.section_number for r in store.rank_chunks(vector, top_k=TOP_K)
        ]
        rank = first_hit_rank(retrieved, acceptable)
        hits += rank is not None
        top_hits += rank == 1
        reciprocal_total += 0.0 if rank is None else 1.0 / rank
        distinct_total += len(set(ranked))

        print(f"{'HIT ' if rank else 'MISS'} {question}")
        print(f"     wanted any of: {', '.join(sorted(acceptable))}")
        print(f"     got:           {', '.join(retrieved)}")
        print(f"     raw chunks:    {', '.join(ranked)}")
        print(f"     first hit at:  {'rank ' + str(rank) if rank else 'not in top 5'}\n")

    count = len(QUESTIONS)
    print(f"recall@{TOP_K}: {hits}/{count}")
    print(f"recall@1:  {top_hits}/{count}")
    print(f"MRR:       {reciprocal_total / count:.3f}")
    print(
        f"distinct sections in the top {TOP_K} chunks: "
        f"{distinct_total / count:.1f} of {TOP_K}"
    )


def main(argv: list[str]) -> int:
    evaluate(argv[1] if len(argv) > 1 else "fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
