"""Configuration for the indexing and query pipelines.

Everything here is a knob the two pipelines read but never write. Keeping the
corpus scope, the snapshot date, and the embedding model in one place is what
makes an index reproducible: the provenance header written by :mod:`store`
is assembled from these values, and :mod:`search` refuses to run against an
index whose header disagrees with them.
"""

#: The eCFR snapshot to index. The versioner API serves a point-in-time edition
#: for any date, so pinning this makes the corpus a fixed artifact rather than
#: "whatever the site said the day you ran it". A regulatory answer without an
#: as-of date is wrong, so this value travels all the way to the citation.
SNAPSHOT_DATE: str = "2026-08-01"

#: Title 31 — Money and Finance: Treasury. Chapter X is FinCEN.
CFR_TITLE: int = 31

#: The parts to index, as strings because CFR part numbers are identifiers and
#: not quantities. This is a subset of Chapter X: 1010 (general provisions),
#: 1020 (banks), and 1022 (money services businesses) — 126 sections.
#:
#: 1020 and 1022 are the load-bearing pair. Their suspicious-activity-report
#: sections are near-identical boilerplate that differ mainly in the entity and
#: the dollar threshold ($5,000 for banks, $2,000 for MSBs), which is exactly
#: the retrieval failure this project is built to expose.
#:
#: The full chapter is parts 1010 and 1020-1032 plus 1060; widening this list is
#: the only change needed to index it.
PARTS: tuple[str, ...] = ("1010", "1020", "1022")

#: Chunks and queries must be embedded by the same model — different models
#: produce incompatible vector spaces, and cosine distances between them are
#: meaningless numbers rather than errors. This is the most common silent
#: failure in a retrieval pipeline, so `store` records the model in the index
#: header and `search` refuses to run on a mismatch.
EMBEDDING_MODEL: str = "text-embedding-3-small"

#: Native output width of EMBEDDING_MODEL. Recorded in the index header so a
#: dimension change is caught at load time rather than inside the dot product.
EMBEDDING_DIMENSIONS: int = 1536

#: Inputs per embeddings request. This is batching, not concurrency: one
#: sequential HTTP call carrying a list. The request stays well inside the
#: endpoint's per-call token ceiling at this chunk size.
EMBEDDING_BATCH_SIZE: int = 128

#: Transport retries, applied by the SDK with exponential backoff for 429/5xx
#: and connection errors.
DEFAULT_MAX_RETRIES: int = 3

#: Fixed-size chunker: window and overlap, in characters. Deliberately naive —
#: this strategy exists to be measured against `structural`, not to win.
FIXED_CHUNK_CHARS: int = 1000
FIXED_CHUNK_OVERLAP: int = 200

#: Structural chunker: the size above which a section is split at its top-level
#: paragraph boundaries. ~6000 characters is roughly 1700 tokens of
#: citation-dense legal English, which leaves generous headroom under the
#: model's 8192-token input limit even when the heading path is prepended.
MAX_CHUNK_CHARS: int = 6000

#: Results returned by a query, after collapsing to one chunk per section.
DEFAULT_TOP_K: int = 5
