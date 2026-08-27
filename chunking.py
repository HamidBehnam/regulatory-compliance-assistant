"""Splitting regulations into retrievable units.

Chunking is the hard part, and it is a content decision rather than a
character count. A chunk has to be self-contained enough to be understood
alone, because alone is how it will be read.

Two strategies live here side by side so they can be measured against each
other. ``fixed_size`` is the naive one, kept rather than replaced: the failure
it produces on this corpus is the thing worth understanding, and you cannot
argue for the structural version without it.
"""

import re
from collections.abc import Callable

from config import FIXED_CHUNK_CHARS, FIXED_CHUNK_OVERLAP, MAX_CHUNK_CHARS
from models import Chunk, Section

#: A line beginning a top-level lettered paragraph: "(a) ", "(ff) ".
#: CFR sections are numbered down to (a)(2)(i)(A)(1); only the outermost level
#: is used as a split point, because that is where a self-contained obligation
#: — or a single defined term — begins.
_TOP_LEVEL_PARAGRAPH = re.compile(r"^\(([a-z]{1,2})\)\s", re.MULTILINE)


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


def structural(
    sections: list[Section], *, max_chars: int = MAX_CHUNK_CHARS
) -> list[Chunk]:
    """Split on the structure the document already has, and keep the path.

    Two changes from ``fixed_size``, and both matter:

    Every chunk carries its heading path — citation, part, subpart, section
    heading — into the embedded text. 31 CFR Chapter X is organized by
    regulated entity, so §1020.320 and §1022.320 are near-identical
    boilerplate that differ mainly in one noun and one dollar figure. Without
    the path in the vector, nothing distinguishes them; with it, "money
    services businesses" is in the embedding of every fragment of 1022.

    Splits happen at top-level paragraph boundaries rather than at character
    offsets, so a definition or an obligation arrives whole. Where a single
    paragraph is still too long, this falls back to fixed-size windows within
    it — the naive strategy is not wrong, it is the last resort you reach for
    when the structure runs out.

    Args:
        sections: Sections in document order.
        max_chars: The size above which a section is split.

    Returns:
        Chunks whose heading path is embedded alongside the regulation text,
        and whose body is regulation text only.
    """
    chunks: list[Chunk] = []
    for section in sections:
        if not section.body.strip():
            continue
        pieces = _split_section(section.body, max_chars=max_chars)
        for index, (label, body) in enumerate(pieces):
            # The paragraph label goes into the path so that a dozen fragments
            # of one long section are not near-duplicates of each other,
            # crowding every other section out of the results.
            heading_path = (
                f"{section.heading_path} — paragraph ({label})"
                if label
                else section.heading_path
            )
            chunks.append(
                Chunk(
                    chunk_id=f"{section.number}#{index}",
                    section_number=section.number,
                    citation=section.citation,
                    heading_path=heading_path,
                    body=body,
                    snapshot_date=section.snapshot_date,
                    source_url=section.source_url,
                )
            )
    return chunks


def _split_section(body: str, *, max_chars: int) -> list[tuple[str | None, str]]:
    """Return (paragraph label, text) pairs for one section."""
    if len(body) <= max_chars:
        return [(None, body)]

    paragraphs = _top_level_paragraphs(body)
    if len(paragraphs) <= 1:
        # No usable structure — window it, and say so by leaving the label off.
        return [(None, w) for w in _windows(body, size=max_chars, overlap=200)]

    pieces: list[tuple[str | None, str]] = []
    for label, text in paragraphs:
        if len(text) <= max_chars:
            pieces.append((label, text))
        else:
            # A single paragraph larger than the cap. Fall back to fixed-size
            # inside it, keeping the label so every window still says which
            # paragraph it came from.
            pieces.extend(
                (label, w) for w in _windows(text, size=max_chars, overlap=200)
            )
    return pieces


def _top_level_paragraphs(body: str) -> list[tuple[str, str]]:
    """Split a section body at its "(a)", "(b)", "(ff)" boundaries."""
    matches = list(_TOP_LEVEL_PARAGRAPH.finditer(body))
    if not matches:
        return []

    paragraphs: list[tuple[str, str]] = []
    # Anything before the first "(a)" is the section's own preamble, which
    # applies to every paragraph under it and so is kept as its own piece.
    preamble = body[: matches[0].start()].strip()
    if preamble:
        paragraphs.append(("preamble", preamble))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        paragraphs.append((match.group(1), body[match.start() : end].strip()))
    return paragraphs


#: Strategies, by the name you pass to index.py and search.py.
CHUNKERS: dict[str, Callable[[list[Section]], list[Chunk]]] = {
    "fixed": fixed_size,
    "structural": structural,
}
