"""Domain errors raised by the indexing and query pipelines.

Transport and payload failures are translated into these at the module
boundary, so callers handle one family of exceptions instead of reaching for
`httpx`, `openai`, or `xml.etree` types of their own.
"""


class RegulatoryAssistantError(Exception):
    """Base class for every failure this project raises."""


class EcfrUnavailable(RegulatoryAssistantError):
    """The eCFR API could not be reached, or returned a non-success status."""


class EcfrUnexpectedPayload(RegulatoryAssistantError):
    """The eCFR API returned a well-formed response that is not what we asked for.

    Worth its own class because the API's failure mode here is silence: an
    unsupported filter parameter is ignored rather than rejected, so a request
    for one chapter comes back as the whole title with a 200 status. Only a
    count check against the structure tree catches it.
    """


class EmbeddingUnavailable(RegulatoryAssistantError):
    """The embeddings API was unreachable or kept failing after SDK retries."""


class IndexStale(RegulatoryAssistantError):
    """The index on disk was not built with the configuration now in effect.

    Querying across an embedding-model or dimension change produces plausible
    rankings from meaningless distances, which is worse than a crash. This is
    raised at load time so that never happens.
    """
