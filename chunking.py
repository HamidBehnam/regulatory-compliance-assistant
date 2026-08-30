"""Two chunking strategies, side by side, so they can be measured against
each other. The comparison is the deliverable; neither one is scaffolding."""

import re
from itertools import pairwise

from models import Chunk, Section

FIXED_CHUNK_CHARS = 1000
FIXED_CHUNK_OVERLAP = 200

# The size above which a section is split. ~6000 characters is roughly 1700
# tokens of citation-dense legal English, well under the embedding model's
# 8192-token input limit even with the heading path prepended.
MAX_CHUNK_CHARS = 6000

# A line beginning a lettered paragraph: "(a) ", "(ff) ", and "(b)(1) ", where
# the label runs straight into its sub-label. This matches lettered labels at
# any depth; which of them are top level is settled by `_top_level_paragraphs`.
_LETTERED_PARAGRAPH = re.compile(r"^\(([a-z]{1,2})\)(?=[\s(])", re.MULTILINE)

# The inverse of the locator `structural` appends to a heading path. Both live
# here so one module owns the format; a checker that re-derived this pattern
# would silently stop matching the day the format changed.
_LOCATOR = re.compile(
    r" — (?:paragraph \(([a-z]{1,2})\)|preamble)(?:, part \d+ of \d+)?$"
)


def paragraph_label(heading_path: str) -> str | None:
    """The top-level paragraph letter ``heading_path`` claims, if it claims one."""
    match = _LOCATOR.search(heading_path)
    return match.group(1) if match else None


def fixed_size(sections: list[Section]) -> list[Chunk]:
    """Split each section into fixed-width windows with a fixed overlap.

    The heading line is left where the source puts it, so only the first window
    of a section carries it. That is not a strawman — it is what windowing over
    a document does, and it is the failure this strategy exists to show.
    """
    chunks: list[Chunk] = []
    for section in sections:
        # Tested on the body, not the heading-plus-body, so `[Reserved]`
        # sections — a heading with no text — drop out of both strategies. The
        # two must cover the same sections or their recall is not comparable.
        if not section.body.strip():
            continue
        text = f"§ {section.number} {section.heading}\n{section.body}".strip()
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
        for index, (locator, body) in enumerate(_split_section(section.body)):
            # The locator keeps a dozen fragments of one long section from
            # being near-duplicates. It is also a claim about the regulation's
            # structure, embedded and printed, so `check_labels.py` holds it to
            # running in sequence and being unique within its section.
            heading_path = section.heading_path
            if locator:
                heading_path += f" — {locator}"
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
    """Return (locator, text) pairs for one section body.

    The locator is the phrase appended to the heading path, or None where the
    piece is the whole section and nothing needs locating.
    """
    if len(body) <= MAX_CHUNK_CHARS:
        return [(None, body)]

    paragraphs = _top_level_paragraphs(body)
    if len(paragraphs) <= 1:
        return [(None, window) for window in _windows_at_cap(body)]

    pieces: list[tuple[str | None, str]] = []
    for label, text in paragraphs:
        locator = "preamble" if label == "preamble" else f"paragraph ({label})"
        if len(text) <= MAX_CHUNK_CHARS:
            pieces.append((locator, text))
            continue
        # A single paragraph over the cap: window inside it, numbering the
        # windows so that each piece's locator stays unique.
        windows = _windows_at_cap(text)
        pieces.extend(
            (f"{locator}, part {n} of {len(windows)}", window)
            for n, window in enumerate(windows, start=1)
        )
    return pieces


def _next_label(label: str) -> str | None:
    """The label following ``label`` in the CFR's top-level run: a…z, aa…zz.

    Two-letter labels are always doubles — aa, bb, never ab — hence the repeat.
    """
    if len(label) == 1:
        return "aa" if label == "z" else chr(ord(label) + 1)
    return None if label[0] == "z" else chr(ord(label[0]) + 1) * 2


def _top_level_paragraphs(body: str) -> list[tuple[str, str]]:
    """Split a section body at its top-level '(a)', '(b)', '(ff)' boundaries.

    A label is top level exactly when it is the one the run needs next: CFR
    top-level paragraphs go a, b, c, … with no gaps, so position in the
    sequence decides what the label's shape cannot. Every other match is
    nested text inside the paragraph that is open.

    Shape cannot decide it because CFR numbering runs (a)(2)(i)(A)(1), making
    the third level lower-case roman numerals — and every short roman numeral
    is also a letter in the top-level run. "(ii)" is the third
    sub-sub-paragraph *and* the 35th top-level paragraph; §1010.100 uses it in
    the latter sense and §1022.320 in the former. The XML cannot decide it
    either: paragraphs are flat <P> siblings carrying no depth attribute.

    A gap in the run ends the walk early and folds the rest of the section into
    the last paragraph reached. `unreached_paragraphs` detects that.
    """
    starts: list[re.Match[str]] = []
    expected: str | None = "a"
    for match in _LETTERED_PARAGRAPH.finditer(body):
        if match.group(1) == expected:
            starts.append(match)
            expected = _next_label(expected)
    if not starts:
        return []

    paragraphs: list[tuple[str, str]] = []
    # Anything before the first "(a)" applies to every paragraph under it, so
    # it is kept as its own piece rather than attached to one of them.
    preamble = body[: starts[0].start()].strip()
    if preamble:
        paragraphs.append(("preamble", preamble))

    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        paragraphs.append((match.group(1), body[match.start() : end].strip()))
    return paragraphs


def unreached_paragraphs(body: str) -> list[tuple[str, str]]:
    """Label pairs proving `_top_level_paragraphs` stopped short of a gap.

    The truncated run a gap leaves is still a valid sequence, so only the text
    folded into the last paragraph reveals one: two labels adjacent in a…z,
    aa…zz. Nested romans are never adjacent there — (i) is followed by (j),
    (ii) by (jj) — which is what keeps this off legitimate nesting.

    Blind to a gap that skips to a single trailing label, which leaves no pair.
    """
    reached = _top_level_paragraphs(body)
    if not reached:
        return []

    _, last = reached[-1]
    labels = [match.group(1) for match in _LETTERED_PARAGRAPH.finditer(last)][1:]
    return [(a, b) for a, b in pairwise(labels) if _next_label(a) == b]


def _windows_at_cap(text: str) -> list[str]:
    """Fall back to fixed-size windows where the document structure runs out.

    Reuses the fixed strategy's overlap: it serves the same purpose here, and
    one knob beats two that would have to be kept in agreement.
    """
    return _windows(text, size=MAX_CHUNK_CHARS, overlap=FIXED_CHUNK_OVERLAP)


def _windows(text: str, *, size: int, overlap: int) -> list[str]:
    """Slide a window of ``size`` over ``text``, stepping by ``size - overlap``."""
    step = size - overlap
    windows = [text[start : start + size] for start in range(0, len(text), step)]
    # Drop a final window lying entirely inside the previous window's overlap,
    # which the last step can produce.
    return [w for i, w in enumerate(windows) if i == 0 or len(w) > overlap]


CHUNKERS = {"fixed": fixed_size, "structural": structural}

# Recorded in the index header: a recall number is comparable to another run
# only if you can see what changed between them.
CHUNKER_PARAMS = {
    "fixed": {"size": FIXED_CHUNK_CHARS, "overlap": FIXED_CHUNK_OVERLAP},
    "structural": {"max_chars": MAX_CHUNK_CHARS},
}
