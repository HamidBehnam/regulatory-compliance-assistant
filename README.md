# regulatory-compliance-assistant

Retrieval over federal AML regulations (31 CFR Chapter X — FinCEN / Bank Secrecy
Act), built from parts rather than a framework.

Two chunking strategies are indexed and scored side by side. Source documents
are cached under `data/raw/`, so only the embedding calls hit the network.

Measured over ten hand-labelled questions at k=5, `text-embedding-3-small`,
2026-08-01 edition:

| | `fixed` (1000/200) | `structural` (max 6000) |
|---|---|---|
| chunks | 570 | 284 |
| recall@5 | 10/10 | 10/10 |
| recall@1 | 10/10 | 9/10 |
| MRR | 1.000 | 0.950 |
| distinct sections in top-5 chunks | 2.6 | 2.9 |

**Null result: structure-aware chunking did not improve any measured metric, and
was marginally worse at rank 1.** recall@5 is saturated for both. The evaluation
set is not strong enough to separate the two — every question names its regulated
entity verbatim, and no metric here looks below the first hit. That blind spot
hides a real difference: on the money-services-business question `fixed` returns a
*bank* section at rank 5 and `structural` returns none, which no number above
moves. See `docs/walkthrough.md` §1 and §4.8.

```
uv run --env-file .env index.py structural
uv run --env-file .env evaluate.py structural
uv run --env-file .env search.py "What is the SAR filing threshold for a bank?" structural
```

Two checks run offline against the cached corpus, and exit non-zero on failure:

```
uv run check_labels.py          # the paragraph locators the structural chunker infers
uv run python -m doctest similarity.py   # the dot product equals the spelled-out cosine
```

## Notes

**Sections loaded in reverse order within each subpart.** `ecfr._walk_sections`
originally walked the XML with an explicit stack that pushed
`reversed(list(element))` and popped, which reverses sibling order at every
level of the hierarchy. Part 1010 came back as 1010.100, 1010.230, 1010.220,
1010.210, … while the function's own docstring claimed document order. The
section-count check against the structure tree passed throughout, because the
*set* of sections was correct and only their order was wrong — nothing in the
pipeline depended on order loudly enough to fail. It is a recursive generator
now, which yields document order by construction.
