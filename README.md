# regulatory-compliance-assistant

Retrieval over federal AML regulations (31 CFR Chapter X — FinCEN / Bank Secrecy
Act), built from parts rather than a framework.

Two chunking strategies are indexed and scored side by side. Source documents
are cached under `data/raw/`, so only the embedding calls hit the network.

```
uv run --env-file .env index.py structural
uv run --env-file .env evaluate.py structural
uv run --env-file .env search.py "What is the SAR filing threshold for a bank?" structural
```

## Notes

**Sections loaded in reverse order within each subpart.** `ecfr._walk_sections`
originally walked the XML with an explicit stack that pushed
`reversed(list(element))` and popped, which reverses sibling order at every
level of the hierarchy. Part 1010 came back as 1010.100, 1010.230, 1010.220,
1010.210, … while the function's own docstring claimed document order. The
section-count check against the structure tree passed throughout, because the
*set* of sections was correct and only their order was wrong — nothing in the
pipeline depended on order loudly enough to fail. It is a recursive generator
now, which yields document order by construction.
