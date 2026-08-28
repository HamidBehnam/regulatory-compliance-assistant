"""Two chunking strategies, side by side, so they can be measured against
each other. The comparison is the deliverable; neither one is scaffolding."""

import re

from models import Chunk, Section

FIXED_CHUNK_CHARS = 1000
FIXED_CHUNK_OVERLAP = 200

# The size above which a section is split. ~6000 characters is roughly 1700
# tokens of citation-dense legal English, well under the embedding model's
# 8192-token input limit even with the heading path prepended.
MAX_CHUNK_CHARS = 6000

# A line beginning a top-level lettered paragraph: "(a) ", "(ff) ". CFR sections
# are numbered down to (a)(2)(i)(A)(1); only the outermost level is used as a
# split point, because that is where a self-contained obligation begins.
_TOP_LEVEL_PARAGRAPH = re.compile(r"^\(([a-z]{1,2})\)\s", re.MULTILINE)


def fixed_size(sections: list[Section]) -> list[Chunk]:
    """Split each section into fixed-width windows with a fixed overlap.

    The heading line is left where the source puts it, so only the first window
    of a section carries it. That is not a strawman — it is what windowing over
    a document does, and it is the failure this strategy exists to show.
    """
    chunks: list[Chunk] = []
    for section in sections:
        text = f"§ {section.number} {section.heading}\n{section.body}".strip()
        if not text:
            continue
        windows = _windows(text, size=FIXED_CHUNK_CHARS, overlap=FIXED_CHUNK_OVERLAP)
        for index, window in enumerate(windows):
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


def structural(sections: list[Section]) -> list[Chunk]:
    """Split on the structure the document already has, and keep the path.

    Chapter X is organized by regulated entity, so §1020.320 and §1022.320 are
    near-identical boilerplate differing mainly in one noun and one dollar
    figure. Carrying the heading path into the embedded text is what puts
    "money services businesses" in the vector of every fragment of 1022.
    """
    chunks: list[Chunk] = []
    for section in sections:
        if not section.body.strip():
            continue
        for index, (label, body) in enumerate(_split_section(section.body)):
            # The paragraph label goes into the path so that a dozen fragments
            # of one long section are not near-duplicates of each other.
            heading_path = section.heading_path
            if label:
                heading_path += f" — paragraph ({label})"
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


def _split_section(body: str) -> list[tuple[str | None, str]]:
    """Return (paragraph label, text) pairs for one section body."""
    if len(body) <= MAX_CHUNK_CHARS:
        return [(None, body)]

    paragraphs = _top_level_paragraphs(body)
    if len(paragraphs) <= 1:
        return [(None, window) for window in _windows_at_cap(body)]

    pieces: list[tuple[str | None, str]] = []
    for label, text in paragraphs:
        if len(text) <= MAX_CHUNK_CHARS:
            pieces.append((label, text))
        else:
            # A single paragraph over the cap: window inside it, keeping the
            # label so every piece still says which paragraph it came from.
            pieces.extend((label, window) for window in _windows_at_cap(text))
    return pieces


def _top_level_paragraphs(body: str) -> list[tuple[str, str]]:
    """Split a section body at its '(a)', '(b)', '(ff)' boundaries."""
    matches = list(_TOP_LEVEL_PARAGRAPH.finditer(body))
    if not matches:
        return []

    paragraphs: list[tuple[str, str]] = []
    # Anything before the first "(a)" applies to every paragraph under it, so
    # it is kept as its own piece rather than attached to one of them.
    preamble = body[: matches[0].start()].strip()
    if preamble:
        paragraphs.append(("preamble", preamble))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        paragraphs.append((match.group(1), body[match.start() : end].strip()))
    return paragraphs


def _windows_at_cap(text: str) -> list[str]:
    """Fall back to fixed-size windows where the document structure runs out."""
    return _windows(text, size=MAX_CHUNK_CHARS, overlap=FIXED_CHUNK_OVERLAP)


def _windows(text: str, *, size: int, overlap: int) -> list[str]:
    """Slide a window of ``size`` over ``text``, stepping by ``size - overlap``."""
    step = size - overlap
    windows = [text[start : start + size] for start in range(0, len(text), step)]
    # The final step can land inside the previous window's overlap and emit a
    # tail that adds nothing.
    return [w for i, w in enumerate(windows) if i == 0 or len(w) > overlap]


CHUNKERS = {"fixed": fixed_size, "structural": structural}

# Recorded in the index header: a recall number is comparable to another run
# only if you can see what changed between them.
CHUNKER_PARAMS = {
    "fixed": {"size": FIXED_CHUNK_CHARS, "overlap": FIXED_CHUNK_OVERLAP},
    "structural": {"max_chars": MAX_CHUNK_CHARS},
}
