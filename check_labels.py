"""Acceptance check for the paragraph locators the structural chunker infers.

    uv run check_labels.py

A locator in a chunk's heading path is a claim about the structure of federal
regulation: "this text is top-level paragraph (d) of § 1022.320". The claim is
embedded into the chunk's vector and printed in search results, so a wrong one
is a wrong answer that nothing else in the pipeline can detect.

Three things fail this check:

**A label out of sequence.** Top-level paragraphs run a, b, c, … z, aa, bb, …
zz with no gaps. A label that does not continue that run is a nested roman
numeral — (ii), (iv), (ix) — that was mistaken for a letter.

**A gap in the run.** The walk stops at the first missing label and folds the
rest of the section into the paragraph it last reached. The run it emits stays
in sequence, so only the text left behind reveals it.

**A duplicate heading path within one section.** Locators exist to keep the
fragments of one section apart in the vector space. Two identical ones are
both a false claim and a pair of near-duplicates.

Exits non-zero if any fails, so it works as a test.
"""

from collections import Counter

from chunking import paragraph_label, structural, unreached_paragraphs
from ecfr import load_sections
from models import Chunk, Section


def _labels_by_section(chunks: list[Chunk]) -> dict[str, list[str]]:
    """Distinct top-level paragraph letters each section emitted, in order."""
    labels: dict[str, list[str]] = {}
    for chunk in chunks:
        label = paragraph_label(chunk.heading_path)
        if label is None:
            continue  # unlabelled piece, or the pre-(a) preamble
        run = labels.setdefault(chunk.section_number, [])
        if not run or run[-1] != label:
            run.append(label)
    return labels


def _expected_sequence(count: int) -> list[str]:
    """The first ``count`` top-level CFR labels: a…z, then aa…zz."""
    letters = [chr(ord("a") + i) for i in range(26)]
    return (letters + [letter * 2 for letter in letters])[:count]


def _out_of_sequence(labels: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        section: run
        for section, run in labels.items()
        if run != _expected_sequence(len(run))
    }


def _gapped(sections: list[Section]) -> dict[str, list[tuple[str, str]]]:
    """Sections whose lettered run has a hole the walk stopped at."""
    gapped: dict[str, list[tuple[str, str]]] = {}
    for section in sections:
        left_behind = unreached_paragraphs(section.body)
        if left_behind:
            gapped[section.number] = left_behind
    return gapped


def _duplicate_paths(chunks: list[Chunk]) -> dict[str, list[str]]:
    """Heading paths emitted more than once within a single section."""
    counts: dict[str, Counter] = {}
    for chunk in chunks:
        counts.setdefault(chunk.section_number, Counter())[chunk.heading_path] += 1

    duplicated: dict[str, list[str]] = {}
    for section, paths in counts.items():
        repeated = [path for path, n in paths.items() if n > 1]
        if repeated:
            duplicated[section] = repeated
    return duplicated


def _print_histogram(labels: dict[str, list[str]]) -> None:
    histogram = Counter(label for run in labels.values() for label in run)
    print("label histogram (most common first):")
    print(
        "  "
        + "  ".join(f"{label}:{n}" for label, n in histogram.most_common(12))
        + (" …" if len(histogram) > 12 else "")
    )
    print(f"  {len(histogram)} distinct labels over {len(labels)} split sections\n")


def _report(title: str, failures: dict[str, list]) -> None:
    print(f"{title}: {len(failures)}")
    for section, detail in sorted(failures.items()):
        print(f"  {section}: {detail}")


def main() -> int:
    sections = load_sections()
    chunks = structural(sections)
    labels = _labels_by_section(chunks)

    # Every check below reads locators back out of the heading paths. If none
    # parsed, the checks are vacuous rather than passing, so say so.
    if not labels:
        print("FAIL — no locators parsed; the check cannot see what it grades")
        return 1

    _print_histogram(labels)

    out_of_sequence = _out_of_sequence(labels)
    gapped = _gapped(sections)
    duplicated = _duplicate_paths(chunks)

    _report("sections whose labels do not run a, b, c, …", out_of_sequence)
    _report("sections with a gap in the lettered run", gapped)
    _report("sections with a duplicated heading path", duplicated)
    print()

    if out_of_sequence or gapped or duplicated:
        print("FAIL — a heading path claims a paragraph that is not top-level")
        return 1
    print("PASS — every locator is a real top-level paragraph, in sequence, unique")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
