"""The data that travels from eCFR XML to a stored vector."""

from pydantic import BaseModel, ConfigDict


class Section(BaseModel):
    """One CFR section, the smallest unit the CFR itself numbers and cites."""

    model_config = ConfigDict(frozen=True)

    number: str
    citation: str
    heading: str
    body: str
    part_heading: str
    subpart_heading: str | None = None
    snapshot_date: str
    source_url: str

    @property
    def heading_path(self) -> str:
        """Where this section sits in the hierarchy, as one line."""
        path = [self.citation, self.part_heading]
        if self.subpart_heading:
            path.append(self.subpart_heading)
        path.append(self.heading)
        return " — ".join(path)


class Chunk(BaseModel):
    """A retrievable unit of text, with everything needed to cite it."""

    model_config = ConfigDict(frozen=True)

    chunk_id: str
    section_number: str
    citation: str
    heading_path: str
    # Regulation text only, kept separate from heading_path so that a
    # verbatim-quote check cannot be satisfied by quoting a heading this code
    # composed rather than the regulation.
    body: str
    snapshot_date: str
    source_url: str

    @property
    def embed_text(self) -> str:
        """Body with its heading path, so near-identical sections in different
        parts of the chapter land in different neighbourhoods of the space."""
        return f"{self.heading_path}\n\n{self.body}" if self.heading_path else self.body


class EmbeddedChunk(BaseModel):
    """A chunk stored alongside its unit-normalized vector.

    Storing the text with the vector is what makes a result citable, and a bad
    result debuggable, without a second source of truth.
    """

    model_config = ConfigDict(frozen=True)

    chunk: Chunk
    vector: list[float]
