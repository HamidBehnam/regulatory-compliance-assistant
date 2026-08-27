"""Splitting regulations into retrievable units.

Chunking is the hard part, and it is a content decision rather than a
character count. A chunk has to be self-contained enough to be understood
alone, because alone is how it will be read.

Two strategies live here side by side so they can be measured against each
other. ``fixed_size`` is the naive one, kept rather than replaced: the failure
it produces on this corpus is the thing worth understanding, and you cannot
argue for the structural version without it.
"""

from collections.abc import Callable

from config import FIXED_CHUNK_CHARS, FIXED_CHUNK_OVERLAP
from models import Chunk, Section


def fixed_size(
    sections: list[Section],
    *,
    size: int = FIXED_CHUNK_CHARS,
    overlap: int = FIXED_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Split each section into fixed-width windows with a fixed overlap.

    The section's own heading line is left at the top of its text, exactly as
    the source presents it — so the *first* window of a section carries the
    heading and every later window does not. That is not a strawman; it is
    what happens when you window over a document, and it is precisely the
    failure this strategy exists to demonstrate.

    Args:
        sections: Sections in document order.
        size: Window width in characters.
        overlap: Characters of the previous window repeated in the next, so a
            sentence cut by one boundary survives whole in a neighbour.

    Returns:
        Chunks with an empty heading path, so nothing but the windowed text is
        embedded.
    """
    if overlap >= size:
        raise ValueError(f"overlap {overlap} must be smaller than size {size}")

    chunks: list[Chunk] = []
    for section in sections:
        text = f"§ {section.number} {section.heading}\n{section.body}".strip()
        if not text:
            continue
        for index, window in enumerate(_windows(text, size=size, overlap=overlap)):
            chunks.append(
                Chunk(
                    chunk_id=f"{section.number}#{index}",
                    section_number=section.number,
                    citation=section.citation,
                    heading_path="",
                    body=window,
                    snapshot_date=section.snapshot_date,
                    source_url=section.source_url,
                )
            )
    return chunks


def _windows(text: str, *, size: int, overlap: int) -> list[str]:
    """Slide a window of ``size`` over ``text``, stepping by ``size - overlap``."""
    step = size - overlap
    windows = [text[start : start + size] for start in range(0, len(text), step)]
    # The final step can land inside the previous window's overlap and emit a
    # tail that adds nothing.
    return [w for i, w in enumerate(windows) if i == 0 or len(w) > overlap]


#: Strategies, by the name you pass to index.py and search.py.
CHUNKERS: dict[str, Callable[[list[Section]], list[Chunk]]] = {
    "fixed": fixed_size,
}
