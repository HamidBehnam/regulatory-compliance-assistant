"""Text to vectors, via the OpenAI embeddings endpoint.

Anthropic does not serve an embedding model, so this half of the system talks
to a different provider than the rest of it.
"""

from functools import cache

from openai import OpenAI, OpenAIError

from config import EMBEDDING_MODEL
from errors import EmbeddingUnavailable

# Inputs per request. This is batching, not concurrency: one sequential HTTP
# call carrying a list, well inside the endpoint's per-call token ceiling.
_BATCH_SIZE = 128

# Applied by the SDK with exponential backoff for 429/5xx and connection errors.
_MAX_RETRIES = 3


def embed(texts: list[str]) -> list[list[float]]:
    """Embed ``texts``, returning one vector each, in input order."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        vectors.extend(_embed_batch(texts[start : start + _BATCH_SIZE]))
    return vectors


@cache
def _client() -> OpenAI:
    """One connection pool per process. The SDK reads OPENAI_API_KEY itself."""
    return OpenAI(max_retries=_MAX_RETRIES)


def _embed_batch(batch: list[str]) -> list[list[float]]:
    try:
        response = _client().embeddings.create(model=EMBEDDING_MODEL, input=batch)
    except OpenAIError as error:
        raise EmbeddingUnavailable(
            f"could not embed a batch of {len(batch)} with {EMBEDDING_MODEL}"
        ) from error

    # The response is not documented to arrive in input order and carries an
    # explicit index per item. Zipping against the inputs would misattribute
    # every vector — all of them valid, all of them on the wrong text.
    return [item.embedding for item in sorted(response.data, key=lambda i: i.index)]
