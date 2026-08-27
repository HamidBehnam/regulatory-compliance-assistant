"""Cosine similarity, written out rather than imported.

Cosine similarity measures the angle between two vectors and ignores their
magnitude. That is the property that matters for embeddings: a long passage
and a short one about the same obligation should score as similar, and the
euclidean distance between them would not say so, because it would be
dominated by how much text each one is.

    cos(a, b) = (a · b) / (|a| |b|)

The division is the normalization. Do it once at index time instead, and every
query afterwards is a plain dot product — the denominator is 1 by construction.
That is the only optimization here, and it is worth understanding rather than
worth hiding: it is the same trick a vector database applies, and knowing it
is why you can say what a vector database is actually buying you.

At this corpus size the answer is: not much. An exact scan over a few thousand
normalized vectors takes single-digit milliseconds in numpy, and stays viable
to roughly 100k vectors. The reason to move to pgvector in a later week is
metadata filtering and hybrid search — "only rules in effect as of March 2024",
"only part 1022" — not speed.
"""

import numpy as np
from numpy.typing import NDArray


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Return the cosine similarity of two vectors, in [-1, 1].

    The explicit form, for one pair. :func:`rank` is what the query path
    actually calls; this exists because the formula should be readable
    somewhere, and because it is what you check ``rank`` against.

    Args:
        left: A vector.
        right: A vector of the same length.

    Returns:
        1.0 when the vectors point the same way, 0.0 when orthogonal.
        Zero when either vector has no magnitude, which has no defined angle.
    """
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denominator == 0.0 else float(np.dot(a, b) / denominator)


def normalize(vector: list[float]) -> list[float]:
    """Scale a vector to unit length, so similarity reduces to a dot product."""
    array = np.asarray(vector, dtype=np.float32)
    magnitude = float(np.linalg.norm(array))
    return array.tolist() if magnitude == 0.0 else (array / magnitude).tolist()


def rank(query: list[float], matrix: NDArray[np.float32]) -> NDArray[np.float32]:
    """Score a query against every row of a matrix of normalized vectors.

    Args:
        query: A unit-length query vector.
        matrix: Shape (n_chunks, n_dimensions), rows already unit-length.

    Returns:
        One score per row, in row order. Brute force over every vector — there
        is no index and no approximation, so the top result is exactly the top
        result rather than probably the top result.
    """
    return matrix @ np.asarray(query, dtype=np.float32)
