"""Turning text into vectors, behind an interface.

The interface is the point. Every implementation is one method — take a list
of strings, return a list of vectors, same order — so swapping providers to
compare them later is a configuration change rather than a rewrite. The
comparison table is the artifact worth having; whichever model happens to win
is not.

Anthropic does not serve an embedding model, so this half of the system talks
to a different provider than the rest of it. That is worth knowing before you
design around a single vendor.

One rule the interface cannot enforce and the caller must not break: chunks and
queries have to go through the *same* model. Different models produce different
vector spaces, and a distance measured between two of them is a number with no
meaning rather than an error. The index header exists to catch that.
"""

from typing import Protocol

from openai import OpenAIError

from clients import get_openai_client
from config import EMBEDDING_BATCH_SIZE, EMBEDDING_MODEL
from errors import EmbeddingUnavailable


class Embedder(Protocol):
    """Anything that can turn text into vectors."""

    @property
    def model(self) -> str:
        """Identifier recorded in the index, and checked before a query runs."""
        ...

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts``, returning one vector each, in the same order."""
        ...


class OpenAIEmbedder:
    """Embeds via the OpenAI embeddings endpoint.

    Requests are batched — one HTTP call carrying many inputs — which is not
    the same thing as concurrency. There is one request in flight at a time and
    no ordering to reason about; it is just the endpoint's own list-shaped API
    used as intended, and it lives entirely behind ``embed``.
    """

    def __init__(
        self, *, model: str = EMBEDDING_MODEL, batch_size: int = EMBEDDING_BATCH_SIZE
    ) -> None:
        self._model = model
        self._batch_size = batch_size

    @property
    def model(self) -> str:
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed ``texts`` in batches.

        Args:
            texts: Strings to embed. Empty list returns an empty list.

        Returns:
            One vector per input, in input order.

        Raises:
            EmbeddingUnavailable: The API was unreachable or kept failing.
        """
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self._batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self._batch_size]))
        return vectors

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """Embed one batch, restoring input order from the response."""
        try:
            response = get_openai_client().embeddings.create(
                model=self._model, input=batch
            )
        except OpenAIError as error:
            raise EmbeddingUnavailable(
                f"could not embed a batch of {len(batch)} with {self._model}"
            ) from error

        # The response carries an explicit `index` per item and is not
        # documented to arrive in input order. Zipping against the inputs would
        # therefore misattribute every vector, silently and without any symptom
        # a test would catch — the vectors are all valid, just on the wrong text.
        return [item.embedding for item in sorted(response.data, key=lambda i: i.index)]
