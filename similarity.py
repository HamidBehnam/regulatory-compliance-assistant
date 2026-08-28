"""Cosine similarity, written out rather than imported.

The formula is spelled out here because it is a deliverable of this project
rather than an implementation detail. :meth:`store.InMemoryStore.search`
computes the same measure as a single dot product over the whole corpus, which
is the right hot path and tells a reader nothing about what is being measured.
"""

import numpy as np


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """The angle between two vectors, ignoring their magnitude.

    Magnitude here is mostly how much text was embedded, so euclidean distance
    would call a long passage and a short one about the same obligation
    dissimilar. Returns zero where either vector has no magnitude and so no
    defined angle.
    """
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denominator == 0.0 else float(np.dot(a, b) / denominator)


def normalize(vector: list[float]) -> list[float]:
    """Scale to unit length at index time, which is what lets the query path
    drop the denominator above and score the corpus with one matrix multiply."""
    array = np.asarray(vector, dtype=np.float32)
    magnitude = float(np.linalg.norm(array))
    return array.tolist() if magnitude == 0.0 else (array / magnitude).tolist()
