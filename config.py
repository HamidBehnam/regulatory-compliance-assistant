"""Values shared by the indexing and query pipelines."""

# Pinning the eCFR edition makes the corpus a fixed artifact rather than
# "whatever the site said that day", and a regulatory answer is incomplete
# without the date its text was in effect.
SNAPSHOT_DATE = "2026-08-01"

# Title 31 — Money and Finance: Treasury. Chapter X is FinCEN.
CFR_TITLE = 31

# A subset of Chapter X: general provisions, banks, money services businesses.
# 1020 and 1022 are the load-bearing pair — their suspicious-activity-report
# sections are near-identical boilerplate differing mainly in the entity and the
# dollar threshold, which is the retrieval failure this project exposes.
PARTS = ("1010", "1020", "1022")

# Chunks and queries must go through the same model: distances between two
# vector spaces are meaningless numbers rather than errors. The index header
# records both of these and `store.InMemoryStore.load` refuses a mismatch.
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

TOP_K = 5
