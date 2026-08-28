"""Errors raised across module boundaries."""


class EcfrError(Exception):
    """The eCFR API was unreachable, or answered with something else."""


class EmbeddingUnavailable(Exception):
    """The embeddings API was unreachable, or kept failing after SDK retries."""


class IndexStale(Exception):
    """The index on disk was not built with the embedding settings now in effect.

    Querying across that change produces well-ordered results from meaningless
    distances, so it is refused at load time rather than allowed to succeed.
    """
