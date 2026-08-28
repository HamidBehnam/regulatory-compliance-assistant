"""Score an index against the hand-labelled questions.

    uv run --env-file .env evaluate.py [fixed|structural]

Reading results by eye is where the understanding comes from, but a retrieval
failure here looks like five plausible passages of regulatory text, one of
which is about the wrong kind of financial institution. Two numbers catch what
reading does not:

**recall@5** — did any acceptable section appear in the top five?

**distinct sections in top 5** — how much of the list is separate sections
rather than fragments of one section shouting over the others.
"""

import sys

from config import TOP_K
from questions import QUESTIONS
from search import search
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
        retrieved = [r.chunk.section_number for r in search(store, question)]
        hit = bool(acceptable.intersection(retrieved))
        hits += hit
        distinct_total += len(set(retrieved))

        print(f"{'HIT ' if hit else 'MISS'} {question}")
        print(f"     wanted any of: {', '.join(sorted(acceptable))}")
        print(f"     got:           {', '.join(retrieved)}\n")

    print(f"recall@{TOP_K}: {hits}/{len(QUESTIONS)}")
    print(f"distinct sections in top {TOP_K}: {distinct_total / len(QUESTIONS):.1f}")


def main(argv: list[str]) -> int:
    evaluate(argv[1] if len(argv) > 1 else "fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
