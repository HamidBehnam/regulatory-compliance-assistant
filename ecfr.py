"""Load 31 CFR sections from the eCFR versioner API.

This is the offline half of the system. It runs when the corpus changes, which
is rarely, so it is written to be slow, cached, and re-runnable rather than
fast: every response is written under ``data/raw/{date}/`` on first fetch and
read from there afterwards. Re-chunking is the thing you do five times in an
afternoon, and it should not cost five round trips to a government API.

Two things about this API shape the code.

The ``full`` endpoint accepts filter parameters, but **silently ignores the
ones it does not support**. ``?chapter=X`` returns HTTP 200 and the entire
9.9 MB of Title 31 — 5,442 sections across nine chapters — rather than the
293 sections of Chapter X. Only ``?part=`` and narrower actually filter. So
this module iterates parts, and then checks the section count of every part it
parsed against the count the structure tree promised. A filter that stops
working degrades into a wrong corpus, not an exception, unless something counts.

Section text is XML, not prose. Naively concatenating the text nodes fuses
words across block boundaries ("...for the bank.The following") and flattens
tables into unreadable runs. Serialization here separates block elements,
keeps inline elements (emphasis, subscripts) inline, and renders table rows as
pipe-delimited lines.
"""

import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from config import CFR_TITLE, PARTS, SNAPSHOT_DATE
from errors import EcfrUnavailable, EcfrUnexpectedPayload
from models import Section

#: Where cached API responses live. Committed to the repository: it is a few
#: hundred KB of US government work in the public domain, and it makes the
#: indexer runnable with no network and reproducible by anyone reading this.
CACHE_ROOT = Path(__file__).parent / "data" / "raw"

_API_ROOT = "https://www.ecfr.gov/api/versioner/v1"
_SITE_ROOT = "https://www.ecfr.gov"

#: eCFR marks its hierarchy with numbered DIV elements rather than named tags.
_SECTION_TAG = "DIV8"
_SUBPART_TAG = "DIV6"
_PART_TAG = "DIV5"

#: Elements that sit inside a sentence and must not introduce whitespace:
#: italics, emphasis, subscripts, superscripts.
_INLINE_TAGS = frozenset({"I", "E", "sub", "sup", "SU"})

#: The literal eCFR writes into hierarchy_metadata paths in place of the
#: requested date, so the caller has to substitute it back in.
_DATE_PLACEHOLDER = "_SUBSTITUTE_DATE_"


def load_sections(
    *,
    parts: tuple[str, ...] = PARTS,
    snapshot_date: str = SNAPSHOT_DATE,
    title: int = CFR_TITLE,
) -> list[Section]:
    """Load every section of ``parts`` as of ``snapshot_date``.

    Args:
        parts: CFR part numbers, as strings.
        snapshot_date: An ISO date. Any date has an edition; the API serves
            the text as it stood that day.
        title: CFR title number.

    Returns:
        Sections in document order, across all parts.

    Raises:
        EcfrUnavailable: The API could not be reached.
        EcfrUnexpectedPayload: A part came back with a different number of
            sections than the structure tree lists for it.
    """
    structure = _fetch_structure(snapshot_date=snapshot_date, title=title)
    expected = _expected_section_counts(structure)

    sections: list[Section] = []
    for part in parts:
        xml = _fetch_part(part=part, snapshot_date=snapshot_date, title=title)
        parsed = _parse_part(xml, part=part, snapshot_date=snapshot_date)

        if part not in expected:
            raise EcfrUnexpectedPayload(
                f"part {part} is not in the {snapshot_date} structure for "
                f"title {title}; check the part number"
            )
        if len(parsed) != expected[part]:
            raise EcfrUnexpectedPayload(
                f"part {part}: structure lists {expected[part]} sections but the "
                f"XML parsed to {len(parsed)}. The full endpoint ignores filter "
                f"parameters it does not support, so an unfiltered response is "
                f"returned with a 200 — check the request URL before the parser."
            )
        sections.extend(parsed)

    return sections


def _fetch_structure(*, snapshot_date: str, title: int) -> dict:
    """Fetch the title's hierarchy tree, which is what enumerates sections."""
    path = CACHE_ROOT / snapshot_date / f"title-{title}-structure.json"
    url = f"{_API_ROOT}/structure/{snapshot_date}/title-{title}.json"
    return json.loads(_cached_get(url=url, path=path))


def _fetch_part(*, part: str, snapshot_date: str, title: int) -> str:
    """Fetch one part's full XML.

    Requests ``?part=`` specifically. Anything broader is not honoured, and
    fails silently rather than loudly — see the module docstring.
    """
    path = CACHE_ROOT / snapshot_date / f"title-{title}-part-{part}.xml"
    url = f"{_API_ROOT}/full/{snapshot_date}/title-{title}.xml?part={part}"
    return _cached_get(url=url, path=path)


def _cached_get(*, url: str, path: Path) -> str:
    """Return the body at ``url``, reading from and writing through ``path``."""
    if path.exists():
        return path.read_text(encoding="utf-8")

    try:
        with urllib.request.urlopen(url, timeout=120) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raise EcfrUnavailable(f"eCFR returned {error.code} for {url}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise EcfrUnavailable(f"could not reach eCFR at {url}") from error

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return body


def _expected_section_counts(structure: dict) -> dict[str, int]:
    """Count the sections the structure tree lists under each part.

    This is the independent number the parsed XML is checked against.
    """
    counts: dict[str, int] = {}

    def visit(node: dict, part: str | None) -> None:
        node_type = node.get("type")
        if node_type == "part":
            part = node.get("identifier")
            counts.setdefault(part, 0)
        elif node_type == "section" and part is not None:
            counts[part] += 1
        for child in node.get("children") or ():
            visit(child, part)

    visit(structure, None)
    return counts


def _parse_part(xml: str, *, part: str, snapshot_date: str) -> list[Section]:
    """Turn one part's XML into Sections, carrying the hierarchy down."""
    root = ET.fromstring(xml)

    part_element = next((e for e in root.iter(_PART_TAG) if e.get("N") == part), None)
    if part_element is None:
        raise EcfrUnexpectedPayload(f"no PART element for {part} in the response")
    part_heading = _clean_part_heading(_head_of(part_element))

    sections: list[Section] = []
    for subpart, subpart_heading, element in _walk_sections(part_element):
        number = element.get("N") or ""
        heading_text = _head_of(element)
        sections.append(
            Section(
                number=number,
                citation=_citation(element, fallback=f"31 CFR {number}"),
                heading=_strip_section_number(heading_text, number=number),
                body=_normalize(_serialize(element, skip_head=True)),
                part=part,
                part_heading=part_heading,
                subpart=subpart,
                subpart_heading=subpart_heading,
                snapshot_date=snapshot_date,
                source_url=_source_url(element, snapshot_date=snapshot_date),
            )
        )
    return sections


def _walk_sections(part_element: ET.Element):
    """Yield (subpart, subpart heading, section element) in document order.

    Sections do not record their own subpart, so the walk carries it down.
    Some parts place sections directly under the part with no subpart at all.
    """
    stack: list[tuple[ET.Element, str | None, str | None]] = [
        (part_element, None, None)
    ]
    while stack:
        element, subpart, subpart_heading = stack.pop()
        for child in reversed(list(element)):
            if child.tag == _SECTION_TAG:
                yield subpart, subpart_heading, child
            elif child.tag == _SUBPART_TAG:
                stack.append(
                    (child, child.get("N"), _clean_subpart_heading(_head_of(child)))
                )
            elif child.tag.startswith("DIV"):
                stack.append((child, subpart, subpart_heading))


def _head_of(element: ET.Element) -> str:
    """Return an element's own HEAD text, ignoring its descendants' headings."""
    head = element.find("HEAD")
    if head is None:
        return ""
    return _normalize(_serialize(head, skip_head=False))


def _serialize(element: ET.Element, *, skip_head: bool) -> str:
    """Render an element's text with block structure preserved.

    Block elements are separated by newlines so sentences do not fuse across
    them; inline elements are concatenated with no separator so emphasis and
    subscripts do not split words; table rows become pipe-delimited lines.
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


def _citation(element: ET.Element, *, fallback: str) -> str:
    """Read the citation eCFR already computed, rather than building one."""
    metadata = element.get("hierarchy_metadata")
    if not metadata:
        return fallback
    try:
        return json.loads(metadata).get("citation") or fallback
    except json.JSONDecodeError:
        return fallback


def _source_url(element: ET.Element, *, snapshot_date: str) -> str:
    """Build a permalink to this section as of the snapshot date.

    eCFR writes a placeholder where the date belongs, so the date the caller
    asked for has to be substituted back in — it is not in the payload.
    """
    metadata = element.get("hierarchy_metadata")
    if not metadata:
        return _SITE_ROOT
    try:
        path = json.loads(metadata).get("path", "")
    except json.JSONDecodeError:
        return _SITE_ROOT
    return _SITE_ROOT + path.replace(_DATE_PLACEHOLDER, snapshot_date)


def _strip_section_number(heading: str, *, number: str) -> str:
    """Turn '§ 1020.220 Customer identification...' into the heading alone."""
    prefix = f"§ {number}"
    return (
        heading.removeprefix(prefix).strip() if heading.startswith(prefix) else heading
    )


#: Words that stay lowercase inside a title-cased heading unless they lead it.
_MINOR_WORDS = frozenset({"a", "an", "and", "by", "for", "in", "of", "or", "the", "to"})


def _clean_part_heading(heading: str) -> str:
    """Turn 'PART 1020—RULES FOR BANKS' into 'Rules for Banks'.

    Part headings are shouted in the source. Title-casing them keeps the
    embedded heading path reading like the prose it sits above.
    """
    _, _, name = heading.partition("—")
    words = (name or heading).strip().title().split()
    return " ".join(
        word if index == 0 or word.lower() not in _MINOR_WORDS else word.lower()
        for index, word in enumerate(words)
    )


def _clean_subpart_heading(heading: str) -> str:
    """Turn 'Subpart B—Programs' into 'Programs'."""
    _, _, name = heading.partition("—")
    return (name or heading).strip()
