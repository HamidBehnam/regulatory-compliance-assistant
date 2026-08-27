"""Where vectors live between the two pipelines.

This is a Python list. That is the correct storage for a corpus this size, and
saying so plainly is more useful than reaching for a database that would hide
what the query path actually does.

The two pipelines connect only here. Indexing writes a file; querying reads it
and never touches a source document. That separation is why the store can be
replaced later — with pgvector, for metadata filtering and hybrid search —
without either pipeline changing shape.

The file is JSONL with a provenance header on the first line: the snapshot
date, the embedding model, the dimensions, the chunker and its parameters.
The header is not documentation. :meth:`InMemoryStore.load` refuses to return
a store whose header disagrees with the configuration now in effect, because
querying a corpus embedded by one model with a vector produced by another
returns confident, well-ordered, meaningless results.
"""

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel

from errors import IndexStale
from models import Chunk, EmbeddedChunk
from similarity import rank

#: Where built indexes live. Gitignored — they are derived from the committed
#: raw corpus, and rebuilding is one command.
INDEX_ROOT = Path(__file__).parent / "data"


class IndexHeader(BaseModel):
    """What produced this index. First line of every index file."""

    snapshot_date: str
    embedding_model: str
    dimensions: int
    chunker: str
    chunker_params: dict[str, int]
    chunk_count: int
    section_count: int


class SearchResult(BaseModel):
    """One retrieved chunk and the score that retrieved it."""

    chunk: Chunk
    score: float


class InMemoryStore:
    """Vectors, text, and metadata, held together and scanned exhaustively."""

    def __init__(self, *, header: IndexHeader, chunks: list[EmbeddedChunk]) -> None:
        self.header = header
        self.chunks = chunks
        #: Vectors stacked once at load so each query is a single matrix
        #: multiply rather than a Python loop over thousands of dot products.
        self._matrix: NDArray[np.float32] = (
            np.array([c.vector for c in chunks], dtype=np.float32)
            if chunks
            else np.zeros((0, header.dimensions), dtype=np.float32)
        )

    def search(
        self, query_vector: list[float], *, top_k: int, one_per_section: bool = True
    ) -> list[SearchResult]:
        """Return the closest chunks to ``query_vector``, best first.

        Args:
            query_vector: A unit-length vector from the *same* model that
                embedded the corpus.
            top_k: How many results to return.
            one_per_section: Keep only each section's best-scoring chunk.
                A long section split into a dozen pieces would otherwise fill
                the whole result list with fragments of itself, crowding out
                every other section — and in this corpus most correct answers
                live in short sections that would lose that fight.

        Returns:
            Up to ``top_k`` results, descending by score.
        """
        if not self.chunks:
            return []

        scores = rank(query_vector, self._matrix)
        order = np.argsort(-scores)

        results: list[SearchResult] = []
        seen: set[str] = set()
        for position in order:
            chunk = self.chunks[int(position)].chunk
            if one_per_section:
                if chunk.section_number in seen:
                    continue
                seen.add(chunk.section_number)
            results.append(
                SearchResult(chunk=chunk, score=float(scores[int(position)]))
            )
            if len(results) == top_k:
                break
        return results

    def save(self, path: Path) -> None:
        """Write the header and one chunk per line."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(self.header.model_dump_json() + "\n")
            for embedded in self.chunks:
                handle.write(embedded.model_dump_json() + "\n")

    @classmethod
    def load(
        cls, path: Path, *, embedding_model: str, dimensions: int
    ) -> InMemoryStore:
        """Read an index, refusing one built under different settings.

        Args:
            path: The .jsonl index file.
            embedding_model: The model the caller is about to embed queries with.
            dimensions: The width that model produces.

        Returns:
            The loaded store.

        Raises:
            IndexStale: The index was built by a different model, or at a
                different width. Both produce a vector space the query vector
                does not live in; a mismatched width would surface eventually
                as a shape error deep inside the dot product, and a mismatched
                model would never surface at all.
        """
        if not path.exists():
            raise IndexStale(f"no index at {path}; build it with index.py")

        with path.open(encoding="utf-8") as handle:
            header = IndexHeader.model_validate_json(next(handle))
            if header.embedding_model != embedding_model:
                raise IndexStale(
                    f"{path.name} was built with {header.embedding_model!r} but "
                    f"queries would be embedded with {embedding_model!r}; distances "
                    f"between two vector spaces are meaningless. Rebuild the index."
                )
            if header.dimensions != dimensions:
                raise IndexStale(
                    f"{path.name} holds {header.dimensions}-dimensional vectors but "
                    f"{embedding_model!r} produces {dimensions}. Rebuild the index."
                )
            chunks = [EmbeddedChunk.model_validate_json(line) for line in handle]

        return cls(header=header, chunks=chunks)


def index_path(strategy: str) -> Path:
    """The conventional location of the index built by ``strategy``."""
    return INDEX_ROOT / f"index-{strategy}.jsonl"
