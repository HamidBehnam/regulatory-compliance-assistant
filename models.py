"""The data that travels through both pipelines.

The indexing pipeline turns eCFR XML into :class:`Section`s, a chunker turns
those into :class:`Chunk`s, and the embedder turns those into
:class:`EmbeddedChunk`s. Nothing else crosses between the two pipelines: the
query side reads :class:`EmbeddedChunk`s back off disk and never touches a
source document.

Two shape decisions carry weight here.

``Chunk`` keeps ``heading_path`` and ``body`` as separate fields rather than
one blob. The embedded text is composed from both, but a quote is only ever
checked against ``body`` — otherwise a grounding check can be satisfied by
quoting a heading this code wrote, rather than regulation text.

Every chunk carries its citation and the snapshot date it was taken from. A
regulatory citation without an as-of date is incomplete, because the answer to
"how long must these records be retained" is a different answer in a different
year, and the whole point of retrieving from the CFR rather than from memory
is being able to say which edition you read.
"""

from pydantic import BaseModel, ConfigDict, Field


class Section(BaseModel):
    """One CFR section, as parsed from an eCFR XML edition.

    A section is the smallest unit the CFR itself numbers and cites, which
    makes it the natural atom here even though its length varies by three
    orders of magnitude across this corpus.
    """

    model_config = ConfigDict(frozen=True)

    number: str = Field(description="Section number, e.g. '1020.220'.")
    citation: str = Field(description="Full citation, e.g. '31 CFR 1020.220'.")
    heading: str = Field(description="Section heading, without the number.")
    body: str = Field(description="Section text, with the heading line removed.")
    part: str = Field(description="Part number, e.g. '1020'.")
    part_heading: str = Field(description="Part heading, e.g. 'Rules for Banks'.")
    subpart: str | None = Field(default=None, description="Subpart letter, if any.")
    subpart_heading: str | None = Field(default=None)
    snapshot_date: str = Field(description="eCFR edition this was read from.")
    source_url: str = Field(description="Permalink to this section at that date.")

    @property
    def heading_path(self) -> str:
        """A one-line description of where this section sits in the hierarchy.

        Prepended to the embedded text by the structural chunker, so that a
        fragment of §1022.320 carries "money services businesses" into its
        vector even when the words appear nowhere in the fragment itself.
        """
        parts = [self.citation, self.part_heading]
        if self.subpart_heading:
            parts.append(self.subpart_heading)
        parts.append(self.heading)
        return " — ".join(parts)


class Chunk(BaseModel):
    """A retrievable unit of text, with everything needed to cite it."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str = Field(description="Stable id, e.g. '1020.220#3'.")
    section_number: str
    citation: str
    heading_path: str
    body: str = Field(description="Regulation text only. Quotes verify against this.")
    snapshot_date: str
    source_url: str

    @property
    def embed_text(self) -> str:
        """What actually gets embedded.

        The heading path is included so that structurally-identical text from
        different parts of the chapter lands in different neighbourhoods of the
        vector space. The fixed-size chunker leaves it empty on purpose.
        """
        return f"{self.heading_path}\n\n{self.body}" if self.heading_path else self.body


class EmbeddedChunk(BaseModel):
    """A chunk and its vector, stored together.

    Storing bare vectors and looking the text up later is the most common early
    mistake in a retrieval system: it makes citation impossible without a second
    source of truth, and it makes debugging a bad result a two-step process.
    """

    model_config = ConfigDict(frozen=True)

    chunk: Chunk
    vector: list[float] = Field(description="Unit-normalized at index time.")
