"""Load 31 CFR sections from the eCFR versioner API.

Every response is cached under ``data/raw/{date}/`` on first fetch, so
re-chunking costs no round trips to a government API.
"""

import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from config import CFR_TITLE, PARTS, SNAPSHOT_DATE
from errors import EcfrError
from models import Section

# Committed to the repository: a few hundred KB of US government work in the
# public domain, which makes the indexer runnable with no network.
CACHE_ROOT = Path(__file__).parent / "data" / "raw"

_API_ROOT = "https://www.ecfr.gov/api/versioner/v1"
_SITE_ROOT = "https://www.ecfr.gov"

# eCFR marks its hierarchy with numbered DIV elements rather than named tags.
_PART_TAG = "DIV5"
_SUBPART_TAG = "DIV6"
_SECTION_TAG = "DIV8"

# Elements that sit inside a sentence and must not introduce whitespace:
# italics, emphasis, subscripts, superscripts.
_INLINE_TAGS = frozenset({"I", "E", "sub", "sup", "SU"})

# eCFR writes this into hierarchy_metadata paths in place of the requested date.
_DATE_PLACEHOLDER = "_SUBSTITUTE_DATE_"


def load_sections() -> list[Section]:
    """Load every configured part as of the snapshot date, in document order."""
    expected = _expected_section_counts(_fetch_structure())

    sections: list[Section] = []
    for part in PARTS:
        parsed = _parse_part(_fetch_part(part), part=part)
        if part not in expected:
            raise EcfrError(
                f"part {part} is not in the {SNAPSHOT_DATE} structure for "
                f"title {CFR_TITLE}; check the part number"
            )
        if len(parsed) != expected[part]:
            raise EcfrError(
                f"part {part}: the structure tree lists {expected[part]} sections "
                f"but the XML parsed to {len(parsed)}. The full endpoint returns 200 "
                f"and the whole title when it does not support a filter parameter, "
                f"so check the request URL before the parser."
            )
        sections.extend(parsed)

    return sections


def _fetch_structure() -> dict:
    """Fetch the title's hierarchy tree, which is what enumerates sections."""
    return json.loads(
        _cached_get(
            url=f"{_API_ROOT}/structure/{SNAPSHOT_DATE}/title-{CFR_TITLE}.json",
            path=CACHE_ROOT / SNAPSHOT_DATE / f"title-{CFR_TITLE}-structure.json",
        )
    )


def _fetch_part(part: str) -> str:
    # Only ?part= and narrower actually filter. ?chapter= is silently ignored
    # and answers with the whole 9.9 MB title, hence the count check above.
    return _cached_get(
        url=f"{_API_ROOT}/full/{SNAPSHOT_DATE}/title-{CFR_TITLE}.xml?part={part}",
        path=CACHE_ROOT / SNAPSHOT_DATE / f"title-{CFR_TITLE}-part-{part}.xml",
    )


def _cached_get(*, url: str, path: Path) -> str:
    """Return the body at ``url``, reading from and writing through ``path``."""
    if path.exists():
        return path.read_text(encoding="utf-8")

    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise EcfrError(f"eCFR returned {error.code} for {url}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise EcfrError(f"could not reach eCFR at {url}") from error

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return body


def _expected_section_counts(structure: dict) -> dict[str, int]:
    """Count the sections the structure tree lists under each part."""
    counts: dict[str, int] = {}

    def visit(node: dict, part: str | None) -> None:
        if node["type"] == "part":
            part = node["identifier"]
            counts.setdefault(part, 0)
        elif node["type"] == "section" and part is not None:
            counts[part] += 1
        for child in node.get("children") or ():
            visit(child, part)

    visit(structure, None)
    return counts


def _parse_part(xml: str, *, part: str) -> list[Section]:
    root = ET.fromstring(xml)

    part_element = next((e for e in root.iter(_PART_TAG) if e.get("N") == part), None)
    if part_element is None:
        raise EcfrError(f"no PART element for {part} in the response")
    part_heading = _title_case(_heading_name(_head_of(part_element)))

    sections: list[Section] = []
    for subpart_heading, element in _walk_sections(part_element):
        number = element.get("N", "")
        metadata = json.loads(element.get("hierarchy_metadata") or "{}")
        path = metadata.get("path", "")
        sections.append(
            Section(
                number=number,
                citation=metadata.get("citation") or f"{CFR_TITLE} CFR {number}",
                heading=_strip_section_number(_head_of(element), number=number),
                body=_normalize(_serialize(element, skip_head=True)),
                part_heading=part_heading,
                subpart_heading=subpart_heading,
                snapshot_date=SNAPSHOT_DATE,
                source_url=_SITE_ROOT + path.replace(_DATE_PLACEHOLDER, SNAPSHOT_DATE),
            )
        )
    return sections


def _walk_sections(element: ET.Element, subpart_heading: str | None = None):
    """Yield (subpart heading, section element) in document order.

    Sections do not record their own subpart, so the walk carries it down, and
    some parts place sections directly under the part with no subpart at all.
    """
    for child in element:
        if child.tag == _SECTION_TAG:
            yield subpart_heading, child
        elif child.tag == _SUBPART_TAG:
            yield from _walk_sections(child, _heading_name(_head_of(child)))
        elif child.tag.startswith("DIV"):
            yield from _walk_sections(child, subpart_heading)


def _head_of(element: ET.Element) -> str:
    """Return an element's own HEAD text, ignoring its descendants' headings."""
    head = element.find("HEAD")
    return "" if head is None else _normalize(_serialize(head, skip_head=False))


def _serialize(element: ET.Element, *, skip_head: bool) -> str:
    """Render an element's text with its block structure preserved.

    Concatenating the text nodes naively fuses words across block boundaries
    ("...for the bank.The following") and flattens tables into unreadable runs.
    """
    if element.tag == "TR":
        cells = (_normalize(_serialize(cell, skip_head=False)) for cell in element)
        return "\n" + " | ".join(cell for cell in cells if cell)

    out: list[str] = []
    if element.text:
        out.append(element.text)
    for child in element:
        if skip_head and child.tag == "HEAD":
            if child.tail:
                out.append(child.tail)
            continue
        rendered = _serialize(child, skip_head=False)
        out.append(rendered if child.tag in _INLINE_TAGS else f"\n{rendered}")
        if child.tail:
            out.append(child.tail)
    return "".join(out)


def _normalize(text: str) -> str:
    """Collapse incidental whitespace without losing paragraph structure."""
    lines = (" ".join(line.split()) for line in text.splitlines())
    return "\n".join(line for line in lines if line).strip()


def _strip_section_number(heading: str, *, number: str) -> str:
    """Turn '§ 1020.220 Customer identification...' into the heading alone."""
    return heading.removeprefix(f"§ {number}").strip()


def _heading_name(heading: str) -> str:
    """Turn 'PART 1020—RULES FOR BANKS' into 'RULES FOR BANKS'."""
    _, _, name = heading.partition("—")
    return (name or heading).strip()


# Articles, conjunctions, and short prepositions stay lowercase inside a
# title-cased heading unless they lead it.
_LOWERCASE_UNLESS_FIRST = frozenset(
    {"a", "an", "and", "by", "for", "in", "of", "or", "the", "to"}
)


def _title_case(heading: str) -> str:
    """Turn the shouted 'RULES FOR BANKS' into 'Rules for Banks'.

    Part headings are upper-case in the source, and this one is both embedded
    as part of every chunk's heading path and printed in search results.
    """
    words = heading.title().split()
    return " ".join(
        word
        if index == 0 or word.lower() not in _LOWERCASE_UNLESS_FIRST
        else word.lower()
        for index, word in enumerate(words)
    )
