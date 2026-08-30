"""The index: chunks, vectors, and a provenance header, in one JSONL file.

The two pipelines connect only here. Indexing writes the file; querying reads
it and never touches a source document.
"""

from pathlib import Path

import numpy as np
from pydantic import BaseModel

from config import EMBEDDING_DIMENSIONS, EMBEDDING_MODEL
from errors import IndexStale
from models import Chunk, EmbeddedChunk

# Gitignored: indexes are derived from the committed raw corpus.
INDEX_ROOT = Path(__file__).parent / "data"


def index_path(strategy: str) -> Path:
    return INDEX_ROOT / f"index-{strategy}.jsonl"


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
    chunk: Chunk
    score: float


class InMemoryStore:
    """Vectors, text, and metadata held together and scanned exhaustively.

    A brute-force scan of a few thousand unit vectors is single-digit
    milliseconds and stays viable to roughly 100k; the reason to move to
    pgvector later is metadata filtering and hybrid search, not speed.
    """

    def __init__(self, header: IndexHeader, chunks: list[EmbeddedChunk]) -> None:
        self.header = header
        self.chunks = chunks
        # Stacked once at load, so each query is one matrix multiply rather
        # than a Python loop over thousands of dot products.
        self._matrix = (
            np.array([c.vector for c in chunks], dtype=np.float32)
            if chunks
            else np.zeros((0, header.dimensions), dtype=np.float32)
        )

    def search(self, query_vector: list[float], *, top_k: int) -> list[SearchResult]:
        """Return the best-scoring chunk of each of the top ``top_k`` sections.

        Collapsing to one chunk per section stops a long section split into a
        dozen pieces from filling the list with fragments of itself; in this
        corpus most correct answers live in short sections that would lose
        that fight.
        """
        results: list[SearchResult] = []
        scores = self._scores(query_vector)
        seen: set[str] = set()
        for position in np.argsort(-scores):
            chunk = self.chunks[position].chunk
            if chunk.section_number in seen:
                continue
            seen.add(chunk.section_number)
            results.append(SearchResult(chunk=chunk, score=float(scores[position])))
            if len(results) == top_k:
                break
        return results

    def rank_chunks(
        self, query_vector: list[float], *, top_k: int
    ) -> list[SearchResult]:
        """Return the top ``top_k`` chunks, without collapsing to one per section.

        This is the ranking `search` filters, exposed so `evaluate` can measure
        how many distinct sections the retrieval actually found. Measuring that
        on `search`'s output cannot work: it dedupes by section, so the count is
        `top_k` by construction and the number can never move.
        """
        scores = self._scores(query_vector)
        return [
            SearchResult(
                chunk=self.chunks[position].chunk, score=float(scores[position])
            )
            for position in np.argsort(-scores)[:top_k]
        ]

    def _scores(self, query_vector: list[float]) -> np.ndarray:
        """Cosine similarity against every stored chunk.

        Every stored vector was unit-normalized at index time, so
        `similarity.cosine_similarity` reduces to a dot product here and one
        matrix multiply scores the whole corpus at once.
        """
        # An empty candidate set is an ordinary result, not a shape error: the
        # zero-row matrix multiplies cleanly and both callers return nothing.
        return self._matrix @ np.asarray(query_vector, dtype=np.float32)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(self.header.model_dump_json() + "\n")
            for embedded in self.chunks:
                handle.write(embedded.model_dump_json() + "\n")

    @classmethod
    def load(cls, path: Path) -> InMemoryStore:
        """Read an index, refusing one whose header disagrees with the config."""
        if not path.exists():
            raise IndexStale(f"no index at {path}; build it with index.py")

        with path.open(encoding="utf-8") as handle:
            header = IndexHeader.model_validate_json(next(handle))
            if header.embedding_model != EMBEDDING_MODEL:
                raise IndexStale(
                    f"{path.name} was built with {header.embedding_model!r} but "
                    f"queries would be embedded with {EMBEDDING_MODEL!r}; distances "
                    f"between two vector spaces are meaningless. Rebuild the index."
                )
            if header.dimensions != EMBEDDING_DIMENSIONS:
                raise IndexStale(
                    f"{path.name} holds {header.dimensions}-dimensional vectors but "
                    f"{EMBEDDING_MODEL!r} produces {EMBEDDING_DIMENSIONS}. "
                    f"Rebuild the index."
                )
            chunks = [EmbeddedChunk.model_validate_json(line) for line in handle]

        return cls(header, chunks)
