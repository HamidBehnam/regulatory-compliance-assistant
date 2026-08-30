# Code walkthrough: regulatory-compliance-assistant

Retrieval over federal anti-money-laundering regulations, built from parts rather than
from a framework.

This document is written for the engineer who owns this codebase and wants to be able to
build a similar system from a blank editor, alone. It is not a tour of the files. It
follows one question from a terminal prompt to a cited paragraph of the Code of Federal
Regulations, and stops at every point where the obvious implementation would have
produced output that looks right and is wrong.

Read it top down. Each section is complete at its own level of detail: you can stop after
section 2 and hold a correct model of the architecture, or stop after section 3 and hold a
correct model of every component.

---

## 1. What this system does, and what goes wrong if it is wrong

### The domain, in one paragraph

The **Code of Federal Regulations** (CFR) is the standing body of US federal regulation,
divided into 50 **titles**. Title 31 is *Money and Finance: Treasury*. Inside it,
**Chapter X** is the rulebook of **FinCEN** — the Financial Crimes Enforcement Network —
which implements the **Bank Secrecy Act**, the statute that requires financial
institutions to keep records and file reports that make money laundering detectable.

Chapter X is divided into **parts**, and this is the fact the whole project turns on:
**the parts are organized by the kind of institution being regulated.**

| Part | Who it governs |
|---|---|
| 1010 | General provisions — definitions and rules that apply to everyone |
| 1020 | Banks |
| 1022 | Money services businesses (check cashers, money transmitters, currency dealers) |

Each part is divided into **sections**, the unit the law itself numbers and cites:
`§ 1020.320`. A section is the smallest thing a compliance officer can point at and say
"this is the rule."

### The users, and the question they ask

The reader is a compliance analyst or a compliance engineer. They ask questions in
ordinary English:

> "What is the SAR filing threshold for a money services business?"

A **SAR** is a Suspicious Activity Report — the form an institution files with Treasury
when it sees a transaction it believes may be criminal. The **threshold** is the dollar
amount at or above which a suspicious transaction must be reported.

They need three things back, and all three are load-bearing:

1. **The text of the rule**, verbatim. Paraphrase is not usable; a compliance file cites
   the regulation as written.
2. **The citation** — `31 CFR 1022.320` — because the answer has to be checkable by
   someone who does not trust the tool.
3. **The date the text was in effect.** Regulations change. An answer without an as-of
   date is not a wrong answer; it is not an answer.

### The failure this project exists to expose — predicted, and not observed

Here are the two sections that govern suspicious activity reports, side by side:

**§ 1020.320** (banks):
> a transaction requires reporting under the terms of this section if it is conducted or
> attempted by, at, or through the bank, it involves or aggregates at least **$5,000** in
> funds or other assets, and the bank knows, suspects, …

**§ 1022.320** (money services businesses):
> … the terms of this section if it is conducted or attempted by, at, or through a
> **money services business**, involves or aggregates funds or other assets of at least
> **$2,000** …

The two sections run to eight and nine thousand characters respectively. They are
near-identical boilerplate. Across their full length they differ in essentially two
things: the noun naming the regulated entity, and the dollar figure.

**The prediction this project was built on.** A naive retrieval system splits every
section into fixed-width windows of text and embeds each window. A window from the middle
of § 1020.320 contains no part heading and no section number — the boilerplate at that
depth, the argument went, talks about "the financial institution" and "the transaction."
A window from the middle of § 1022.320 looks the same. The query embedding cannot tell
them apart, so the MSB question returns § 1020.320: real federal regulation, a real
citation, formatting identical to a correct answer, and $5,000 where the correct answer
for this user is $2,000. Nothing fails, no exception, no low-confidence score, and the
user files — or does not file — accordingly.

**That did not happen.** The prediction was wrong, and it was wrong in a way this
document could have caught before the embedding key ever worked.

Measured, on the `fixed` index, for *"What is the SAR filing threshold for a money
services business?"*. The two rankings show different things and have to be read
separately.

**The raw chunk ranking** — what the embedding actually scored highest, before
`store.search` collapses to one chunk per section (3.7) — is § 1022.320 four times, then
§ 1022.380. No part-1020 chunk appears in it at all. So the top of the list was already
correct on the vectors alone: the collapse did not rescue a correct answer from a crowded
one, and § 1022.320 is returned first by both strategies.

**The collapsed list** — what `search.py` actually prints — is § 1022.320, § 1022.380,
§ 1022.300, § 1022.500, and then, **at rank 5, § 1020.320**. Chunk `1020.320#4`, score
0.565, path `(no heading in the embedded text)`, opening on paragraph (d): *"Retention of
records. A bank shall maintain a copy of any SAR filed … for a period of five years from
the date of filing the SAR."* That is a passage about **banks**, in a results list for a
question about money services businesses, carrying no heading to warn the reader — the
predicted failure, in the predicted form, produced by the predicted mechanism.

So the honest statement is narrower than either "it happened" or "it did not." **The
mechanism is real but far weaker than section 1 originally claimed.** It was predicted to
put § 1020.320 *first*, displacing the correct answer and handing the user $5,000 in place
of $2,000. What it actually does is put § 1020.320 *fifth*, beneath four correct part-1022
results, where it is the last item of a list whose first item already answers the question.
That is a wrong entry in a results list, not a wrong answer.

The gap between those two outcomes is the whole finding, and it is why the raw ranking is
worth printing beside the collapsed one. The raw ranking says the embedding was never
confused about the entity. The collapsed list says that once the four best chunks of the
correct section are deduplicated down to one, a bank chunk is close enough to be the fifth
distinct section in a 117-section corpus. Both are true, and a document that reports only
one of them is misleading in one direction or the other.

For completeness, because it is the comparison this project exists to make: under
`structural` the same query returns § 1022.320, § 1022.380, § 1022.315, § 1022.312 and
§ 1022.300 — **five part-1022 sections and no bank section anywhere in the list.** On this
one question, the heading path does exactly what 3.4.2 says it does. No metric in the
harness can see it, because the entry it removes sits below a rank that was already a hit.

#### Why the prediction was wrong

The claim was that middle windows contain nothing to distinguish the two sections. The
disconfirming evidence is three lines above the claim, inside this document's own
quotation of § 1022.320:

> … conducted or attempted by, at, or through a **money services business** …

The entity name is not confined to the heading. It is in the body text, and it is in the
body text throughout. Counted over the cached corpus:

| Section | Entity term in body | Fixed-size windows containing it |
|---|---|---|
| § 1020.320 | "bank" — 42 occurrences | **10 of 10** |
| § 1022.320 | "money services business" — 36 occurrences | **12 of 12** |

Every window of both sections names its own regulated entity. There was never a window
that "often not even" contained the word. The regulation restates who it binds in nearly
every operative sentence, because that is how regulatory drafting works: statutory text
repeats the defined term rather than pronominalising it, precisely so a paragraph read
alone is unambiguous. The drafting convention that makes the CFR verbose is the same
convention that makes it chunk well — and the argument above assumed the opposite of the
thing that makes this corpus worth using.

The reasoning error is worth more than the failed prediction. It was **an assumption
about what the source text contains, never checked against the source text.** Every other
claim in this document — corpus counts, chunk counts, the label histogram in 4.3 — was
produced by running something over the corpus. This one was produced by imagining what
the corpus looked like, it sat in section 1 through an entire build and an audit, and a
single `grep` would have killed it at any point.

There is a second, independent reason the failure could not have appeared here:
**the evaluation questions name the entity.** *"What is the SAR filing threshold for a
money services business?"* contains verbatim the phrase the regulation uses 36 times in
the body of the very section it should return. That is strong lexical signal, and no
chunking strategy has to work for it to survive into the embedding. A question set built
this way cannot test entity disambiguation whatever the chunker does — see 4.8.

What is retracted is the specific claim that *this* corpus and *this* chunker produce the
confusion. The failure mode as a class is not retracted, and it is the reason for the
shape of everything below: **plausible-looking wrong output, produced by code that ran
without error.** Section 4 is a list of those that were real — a mis-attributed embedding
vector, a locator that lied about the regulation's structure, a metric that could only
ever print one number. The design of the system, and the disproportionate length of that
section, follow from the class. The example that opened this document just turned out not
to be a member of it.

### What was measured

Both indexes built over the 2026-08-01 edition with `text-embedding-3-small` at 1536
dimensions; ten hand-labelled questions (3.9); k = 5.

| | `fixed` (size 1000 / overlap 200) | `structural` (max_chars 6000) |
|---|---|---|
| chunks | 570 | 284 |
| sections | 126 | 126 |
| **recall@5** | 10/10 | 10/10 |
| **recall@1** | **10/10** | **9/10** |
| **MRR** | **1.000** | **0.950** |
| distinct sections in top-5 chunks | 2.6 of 5 | 2.9 of 5 |

**On this corpus, with this evaluation set, structure-aware chunking did not improve
retrieval, and it was marginally worse at rank 1.** That is the result. recall@5 is
identical and saturated at ceiling. recall@1 falls from 10/10 to 9/10 and MRR from 1.000
to 0.950 on a single question — *"What identifying information must a bank obtain before
opening an account?"* — where `structural` ranks § 1010.312 *Identification required.*
above § 1020.220, 0.6484 to 0.6305.

The remaining arguments for `structural` are real, and **none of them is a recall gain**:
obligations arrive whole instead of truncated at character 1000 (3.4.2); the locator
printed with a citation is a true statement about the regulation's structure rather than a
window index (4.3); fewer fragments of one long section crowd the ranking (2.6 → 2.9
distinct sections); 284 chunks cost half of 570 to embed and store; and, on the MSB
question above, it clears the stray bank section out of the results list where `fixed`
leaves it at rank 5. That last one is the entity-ambiguity defence working as designed,
and it is worth being clear that **no number in the table below moves when it does** —
recall@5, recall@1 and MRR are all already satisfied by rank 1, so an improvement at rank
5 is invisible to every metric this harness reports. Those are claims
about the quality and the honesty of what a correct retrieval hands a user. They are not
evidence that it retrieves correctly more often, and this evaluation provides none.

**The one regression has a mechanical explanation, and it is not about structure.**
§ 1020.220 is 12,202 characters. `structural` splits it into four paragraph chunks of
6000, 5473, 573 and 354 characters, so the sentences answering the question sit inside a
6000-character chunk beside several thousand characters of adjacent obligation. `fixed`
puts those same sentences in a 1000-character window that is almost nothing else, and
that window scores 0.7343 — against `structural`'s best 0.6305 on the same section.
§ 1010.312 is 1,598 characters, survives as one whole chunk, and is entirely about
recording a customer's name and address; under `structural` it wins by dilution of its
rival rather than on the merits. **Near the top of a ranking, chunk size dominates chunk
boundaries.** The 6000-character cap was chosen to keep obligations intact and to sit
inside the model's token limit (3.4.2); nothing measured it against retrieval, and this
is the first evidence of what it costs.

### Scope

Parts 1010, 1020, and 1022 as of the 2026-08-01 edition: 126 numbered sections, of which
117 carry text and 9 are `[Reserved]` placeholders that both chunkers skip. That is a
deliberately small corpus. It contains the near-duplicate sections the entity-ambiguity
argument was built on, and it is small enough that you can read a section by hand to check
whether a retrieval was right — which is the only way to build a trustworthy evaluation
set. Whether it is large enough to make two chunking strategies *distinguishable* is a
separate question, and the answer measured above is no; that is 4.8.

Earlier drafts of this document carried no recall number at all — the embedding key had
no quota, and `evaluate.py` had only ever run against stub vectors. That is no longer
true: the table above is measured, on both indexes, with the real model. Where a
statement below is still a prediction from the mechanism rather than a measurement, it
says so. Where a prediction has since been measured and found wrong, it is marked wrong
in place rather than quietly deleted — 3.4.2, 4.4 and 4.8 are the three that matter, and
those paragraphs are the most useful ones here.

---

## 2. The architecture

### Two pipelines that meet at one file

```
OFFLINE (runs when the corpus changes — rarely)

  eCFR versioner API
        │  XML + a JSON structure tree
        ▼
  ecfr.load_sections()        →  126 Section objects, document order
        │
        ▼
  chunking.CHUNKERS[strategy] →  284–570 Chunk objects
        │
        ▼
  embedding.embed()           →  one 1536-float vector per chunk
        │
        ▼
  similarity.normalize()      →  unit-length vectors
        │
        ▼
  store.InMemoryStore.save()  →  data/index-{strategy}.jsonl
                                 ═══════════════════════════
                                   THE ONLY SHARED SURFACE
                                 ═══════════════════════════
ONLINE (runs per query)

  "What is the SAR threshold for an MSB?"
        │
        ▼
  embedding.embed()  →  similarity.normalize()  →  query vector
        │
        ▼
  store.InMemoryStore.load()  →  header check, then vectors in memory
        │
        ▼
  matrix multiply → argsort → collapse to one chunk per section → top 5
        │
        ▼
  citation + as-of date + source URL + text
```

The query path never opens an XML file, never consults the eCFR API, and never re-derives
a chunk. Everything it needs was written into the index. Scoring the whole corpus takes
0.013 ms for the structural index and 0.032 ms for the fixed one, measured on this
machine — the query round trip is entirely the embedding API call. More importantly, it is
what makes a bad result *reproducible*: the index is a file you can open and read.

### Why these boundaries

Each module boundary is drawn where the vocabulary changes. That is the rule, and it is
worth internalizing because it is what lets you rebuild this from scratch without a
framework.

- **`ecfr.py` speaks XML and HTTP.** It knows about `DIV5` elements and cache paths. It
  has never heard of a vector, a chunk, or a similarity score. Its output type is
  `Section`, which is pure domain: a numbered piece of law with a heading and a body.
- **`chunking.py` speaks `Section → Chunk`.** It knows how legal text is structured —
  that `(a)`, `(b)`, `(c)` mark self-contained obligations. It does not know that its
  output will be embedded, and would produce the same chunks if the retrieval were
  keyword-based.
- **`embedding.py` speaks `list[str] → list[list[float]]`.** It is the only module that
  knows a third-party API exists.
- **`store.py` speaks vectors.** It has never seen a section number as anything but an
  opaque grouping key.

The payoff: to swap the embedding provider you edit one file with two functions in it. To
add a third chunking strategy you add one function and one dictionary entry. To index a
different CFR chapter you edit one tuple in `config.py`. Nothing else moves.

**The rejected alternative: a retrieval framework.** LangChain or LlamaIndex would have
supplied the loader, the splitter, the embedder, and the vector store in about forty lines
of glue. The reason not to: every serious failure in this system lives *in a seam* —
between the API's response order and the input order, between the model that built the
index and the model embedding the query, between the heading a chunk carries and the text
it actually contains. A framework's job is to hide seams. You would get a working
prototype faster and you would not be able to see, let alone fix, the entity-ambiguity
failure in section 1. This project's deliverable is the understanding, so the seams are
the product.

**The rejected alternative: a vector database.** pgvector, Chroma, Pinecone. A
brute-force scan of a few thousand unit vectors is well under a millisecond — 0.013 ms
over this corpus, measured — and stays viable to roughly 100,000 vectors. Reaching for an approximate-nearest-neighbour index at
this scale would add a service, a schema, and an approximation — and the approximation is
the worst part, because an ANN index that silently misses a neighbour produces exactly the
plausible-wrong-answer failure this project is built to catch. The honest reason to move
to pgvector later is metadata filtering ("only part 1022") and hybrid keyword+vector
search, not speed. That reasoning is written into `store.InMemoryStore`'s docstring so the
next reader does not mistake the choice for naivety.

**The rejected alternative: one pipeline instead of two.** Fetching and embedding at query
time would eliminate the index file and the staleness class of bug with it. It would also
mean every question costs a call to a government API and 284 embedding calls, and it would
make results irreproducible — you could never re-run a query against the corpus as it was.
The index file is a *commitment*, and the provenance header (section 3.7) is what makes it
an honest one.

---

## 3. The components, following the data

### 3.1 The pinned snapshot — `config.py`

```python
SNAPSHOT_DATE = "2026-08-01"
```

The eCFR versioner API serves a point-in-time edition for any date. Pinning the date makes
the corpus a fixed artifact rather than "whatever the site said the day you ran it."

The obvious alternative is to fetch the current edition. The consequence: two runs a month
apart produce different answers to the same question with no record of why, and a recall
score of 7/10 from March is not comparable to 8/10 from April. Worse, in this domain the
as-of date is part of the answer — the date travels from this constant all the way into
the `Section`, into the `Chunk`, into the index header, and out into the printed result.

`config.py` contains only values that genuinely cross module boundaries: the snapshot
date, the title, the parts, the embedding model and its dimension count, and `TOP_K`.
Chunk sizes live in `chunking.py` and batch sizes live in `embedding.py`, because nothing
else reads them. This is worth copying: a config module that accumulates every constant
becomes a second, worse table of contents for the codebase.

### 3.2 Loading the corpus — `ecfr.py`

**Input:** nothing (the parts and date come from config).
**Output:** `list[Section]`, in document order.

This module runs rarely and is written to be slow, cached, and re-runnable rather than
fast. Four decisions shaped it.

#### 3.2.1 Cache on disk, and commit the cache

`_cached_get` reads through a path under `data/raw/{date}/`, writing the response on first
fetch. The cached files are **committed to the repository** — about 450 KB of XML plus a
1.8 MB structure tree, all US government work in the public domain.

Committing generated data is normally wrong. Here it buys two specific things. First, the
indexer runs with no network, so anyone who clones the repo can re-chunk the corpus five
times in an afternoon without touching a government API. Second, and more important, it
makes the corpus itself reviewable: when a retrieval looks wrong, you open the XML and
read the section. Without the cache the corpus is a side effect of a fetch that may no
longer be reproducible.

The alternative — fetch on demand, cache in a gitignored directory — costs one API round
trip per part per fresh clone, and quietly makes the project's results unverifiable the
day the API changes or the pinned date stops being served.

#### 3.2.2 The count check, and the filter that lies

This is the most instructive thing in the module.

The versioner API's `full` endpoint accepts filter parameters. It **silently ignores the
ones it does not support**. `?chapter=X` returns HTTP 200 and the entire 9.9 MB of Title
31 — 5,442 sections across 211 parts — rather than the sections of Chapter X. Only
`?part=` and narrower actually filter.

Think about what that means for a naive implementation. You request Chapter X. You get
200 OK. You get valid XML. You parse it and get thousands of sections. Your pipeline
embeds all of them, your index builds, your searches return results. The results are drawn
from all of Title 31 — bank secrecy rules mixed with Treasury procurement, foreign asset
control, and savings bond regulations. Nothing failed. Your recall number is garbage and
you have no way to know.

The defence is that `load_sections` never trusts the parse:

```python
if len(parsed) != expected[part]:
    raise EcfrError(
        f"part {part}: the structure tree lists {expected[part]} sections "
        f"but the XML parsed to {len(parsed)}. The full endpoint returns 200 "
        f"and the whole title when it does not support a filter parameter, "
        f"so check the request URL before the parser."
    )
```

`_expected_section_counts` walks a *different* endpoint — the `structure` tree, a JSON
hierarchy of the whole title — and counts the sections it lists under each part. For this
corpus: 81, 24, 21, totalling 126. The XML parse must produce exactly those numbers.

The principle to carry forward: **when an API can degrade into wrong data rather than an
error, find a second, independent source for a count and assert on it.** The check is
cheap, it runs on every load, and it converts an entire class of silent corpus corruption
into a loud failure with a message that names the likely cause. Note the error text points
at the request URL *before* the parser — that is where the bug will actually be, and
saying so saves the next reader an hour.

The check also catches the reverse failure: a parser change that starts dropping sections
because a tag name moved.

#### 3.2.3 Serializing XML into readable text

`_serialize` renders an element's text with block structure preserved. The naive
implementation is `"".join(element.itertext())`, and it is wrong in two ways that do not
announce themselves.

Block elements fuse across boundaries: the last word of one paragraph runs into the first
word of the next, producing `"...for the bank.The following"`. That token is not in the
embedding model's vocabulary in any useful way, and every sentence boundary in the corpus
becomes a small piece of noise.

Tables flatten into unreadable runs of numbers and labels with no structure at all. CFR
sections contain tables of reporting thresholds — exactly the content the highest-value
questions are about.

So `_serialize` does three things: it puts a newline before each block child, it
concatenates inline children with no separator, and it renders each table row as a
pipe-delimited line.

The inline set is the part that is easy to get wrong in the other direction:

```python
_INLINE_TAGS = frozenset({"I", "E", "sub", "sup", "SU"})
```

Italics, emphasis, subscripts and superscripts sit *inside* a sentence. Treat them as
blocks and you split words: a defined term set in italics mid-sentence becomes three
fragments on three lines. Legal text italicizes defined terms constantly, so this is not
an edge case in this corpus — it is most sentences that matter.

`_normalize` then collapses runs of whitespace within each line and drops empty lines,
which preserves paragraph structure while removing the XML's incidental indentation.

#### 3.2.4 The walk that carries the subpart down

Sections do not record which **subpart** they belong to. A subpart is an intermediate
grouping between part and section — "Reports Required To Be Made By Banks" — and it is
useful context for retrieval, so the traversal carries it down:

```python
def _walk_sections(element, subpart_heading=None):
    for child in element:
        if child.tag == _SECTION_TAG:
            yield subpart_heading, child
        elif child.tag == _SUBPART_TAG:
            yield from _walk_sections(child, _heading_name(_head_of(child)))
        elif child.tag.startswith("DIV"):
            yield from _walk_sections(child, subpart_heading)
```

The third branch matters: the hierarchy has levels this code does not care about
(`DIV7`, subject groups), and descending through them while keeping the current subpart is
what stops sections from losing their context at an arbitrary nesting depth. The
`startswith("DIV")` catch-all is deliberate — it means an unfamiliar hierarchy level is
traversed rather than silently pruned. If eCFR introduces a new `DIVn`, this code finds
the sections under it; the count check would have caught the alternative.

This function is also where the one real bug found during the build lived. Section 4.2.

### 3.3 The data model — `models.py`

Three frozen Pydantic models, and one design decision worth all the space it gets.

`Section` is one CFR section: number, citation, heading, body, part heading, subpart
heading, snapshot date, source URL. `Chunk` is a retrievable unit. `EmbeddedChunk` is a
chunk plus its vector.

#### The heading_path / body split

`Chunk` has two text fields and they are never merged in storage:

```python
class Chunk(BaseModel):
    heading_path: str  # composed by this code
    body: str  # regulation text, verbatim

    @property
    def embed_text(self) -> str:
        return f"{self.heading_path}\n\n{self.body}" if self.heading_path else self.body
```

`heading_path` is assembled by `Section.heading_path` and looks like:

```
31 CFR 1022.320 — Rules for Money Services Businesses — Reports Required To Be
Made By Money Services Businesses — Reports by money services businesses of
suspicious transactions. — paragraph (a)
```

The obvious implementation is to prepend the heading to the body once, at chunk time, and
store one `text` field. It is simpler, it produces the identical embedding, and it is
wrong.

**What it costs you:** the heading path is *not regulation text*. It contains a part
heading this code title-cased, a citation this code composed from metadata, and a
paragraph label this code inferred with a regular expression. The body is the only part
that is verbatim law.

The moment you build the natural next component — a generation layer that answers in prose
and must ground every claim in a quoted passage of the regulation — you need a check that
the quote appears in the source. If heading and body are one string, that check passes on
a quote of `"Rules for Money Services Businesses"`, which is a phrase this code invented.
The system would then *certify* a hallucinated citation. Keeping the two apart makes the
verbatim check checkable against the only field that can honestly satisfy it.

The same split shows up in the printed output: `search.format_result` prints the path on
its own labelled line, so a reader can never mistake composed context for quoted law.

This is the general lesson: **when your pipeline synthesizes text and mixes it with source
text, keep a field boundary between them, even when nothing today reads them separately.**
Merging is a one-line change later; un-merging after downstream code has assumed one field
is not.

### 3.4 Chunking — `chunking.py`

**Input:** `list[Section]`. **Output:** `list[Chunk]`.

Both strategies live here, side by side, and neither is scaffolding. The comparison is the
deliverable: you cannot argue for the structural chunker without the naive one to measure
it against, and a reader who is handed only the good version learns the answer without
learning the problem.

#### 3.4.1 `fixed_size` — the strategy that fails, kept on purpose

Splits each section into 1000-character windows with 200 characters of overlap. The
overlap exists so a sentence cut by one boundary survives whole in a neighbour.

Two properties make it fail, and both are faithful to what real fixed-size chunking does.

The first: the heading is left where the source puts it, at the top of the text.

```python
text = f"§ {section.number} {section.heading}\n{section.body}".strip()
```

So **only the first window of a section carries the heading.** § 1020.320 produces 10
windows; nine of them contain no section number and no part heading.

The second: `fixed_size` passes `heading_path=""` when it builds each `Chunk`, so
`embed_text` returns the window alone. Nothing but the raw text goes into the vector.

This is not a strawman built to lose. It is exactly what windowing over a document does.
Every off-the-shelf character splitter behaves this way by default.

The concrete result, from window 3 of each section:

- `1020.320#3`: *"…a bank may delay filing a SAR for an additional 30 calendar days to identify a suspect…"*
- `1022.320#3`: *"…transactions that involves or aggregates funds or other assets of at least $5,000. (4) The obligation to identify and properly and timely to report a suspicious transaction rests with each money services business…"*

Look at the second one carefully. It is a window from the **MSB** section, and the dollar
figure in it is **$5,000** — because § 1022.320 contains both thresholds. $2,000 is the
general reporting duty. $5,000 applies only to an issuer of money orders or traveler's
checks whose suspicion is derived from a review of clearance records. A retrieval system that
returns this window in answer to "what is the SAR threshold for an MSB" has returned the
right *section* and a passage that will be read as the wrong *answer*. Fixed-size chunking
does not just confuse two sections; it strands a number away from the sentence that
qualifies it.

#### 3.4.2 `structural` — split where the document already splits

Two changes, and both are necessary. Either one alone leaves the failure in place.

**Change one: carry the heading path into the embedded text.** Every chunk of § 1022.320,
including the seventh, has "Money Services Businesses" in its vector. The near-identical
boilerplate lands in a different neighbourhood of the embedding space from part 1020's
copy of it.

**This was written as the fix for the failure in section 1, and the failure it was aimed
at is much smaller than section 1 originally claimed.** `fixed` already returns § 1022.320
at rank 1 for the MSB question carrying no heading path at all, because the regulation
names its own regulated entity in all twelve of that section's windows. At the top of the
ranking, where the answer is decided, the heading path is redundant with the body text.

**Where it does still work is further down the list.** `fixed` leaves § 1020.320 — a
passage about a *bank's* SAR retention — at rank 5 of the collapsed results for the MSB
question. `structural` returns five part-1022 sections and no bank section at all. That is
this change doing precisely what it was designed to do, measured rather than reasoned: the
part heading in the vector is what pushes the 1020 boilerplate below the 1022 boilerplate
once the correct section has been deduplicated to a single entry.

It is a smaller prize than advertised, and it costs nothing to be exact about the size.
The claim was that this change decides the *answer*; what it decides is the *tail of the
results list*. Since rank 1 was already correct without it, **no metric in the harness
moves** — recall@5, recall@1 and MRR are all settled by the first entry, which is why
section 1 reports a null result while this paragraph reports a real effect. Those are
consistent, and the reason they are consistent is that the evaluation cannot see below the
first hit (4.8).

Two further reasons the mechanism stays, independent of any of that. It is what makes a
chunk's *printed* context true — a result listing that shows `31 CFR 1022.320 — Rules for
Money Services Businesses — … — paragraph (d)` tells a compliance officer where they are,
and `fixed` prints `(no heading in the embedded text)` (3.8). And within a section it is
the only thing distinguishing one fragment from another, which is the crowding defence
discussed below. What is retracted is the claim that this change is what stands between
the user and a $5,000 answer to a $2,000 question. Keep the mechanism; shrink the claim.

**Change two: split at top-level paragraph boundaries, not character offsets.** CFR
sections are numbered down to `(a)(2)(i)(A)(1)`. The outermost level — `(a)`, `(b)`,
`(ff)` — is where a self-contained obligation or a single defined term begins. Splitting
there means a definition arrives whole rather than truncated at character 1000.

The control flow in `_split_section` is a three-level fallback, and the ordering is the
design:

1. Section under the 6000-character cap → one chunk, no split. Most sections (98 of the
   117 with text; the median body is 732 characters) never split at all. **This is the
   most important line in the file.** A section that fits should not be chunked, because
   every split is an opportunity to separate an obligation from its qualifier.
2. Section over the cap with detectable paragraph structure → one chunk per top-level
   paragraph. Anything before the first `(a)` becomes a chunk located as `preamble`,
   because it applies to every paragraph beneath it and attaching it to `(a)` would be a
   lie. § 1020.320 and § 1022.320 each yield exactly seven chunks here, (a) through (g).
3. A single paragraph still over the cap → fixed-size windows *inside* it, numbered
   `part 2 of 3`. The naive strategy is not wrong; it is the last resort you reach when
   the document's own structure runs out.

The 6000-character cap is roughly 1700 tokens of citation-dense legal English, comfortably
inside the embedding model's 8192-token input limit even with the heading path prepended.
The alternative — setting the cap at the model's actual limit — saves nothing and risks a
runtime rejection on the one section that runs long.

The **locator** — the phrase naming which part of the section a chunk is — goes into the
heading path:

```python
heading_path = section.heading_path
if locator:
    heading_path += f" — {locator}"
```

Without it, a dozen fragments of one long section are near-duplicates of each other in
embedding space — same citation, same part, same section heading, similar boilerplate.
They would then crowd each other in the results list, and the locator is what gives each
one a distinguishing token. (This is a partial defence. The full defence is in
`store.search`; see 3.7.)

Two things follow from the locator being *embedded and printed* rather than internal. It
is a claim about the structure of federal regulation, so it has to be true; and it only
does its job if it is unique within a section, so two pieces of paragraph (a) must not
both read "paragraph (a)". Both properties were broken, in ways nothing detected, and
`check_labels.py` now holds them. That is section 4.3 — the longest entry in this
document, because it is the kind of bug it exists to teach.

#### 3.4.3 The window function, and the tail that lies inside its predecessor

```python
def _windows(text, *, size, overlap):
    step = size - overlap
    windows = [text[start : start + size] for start in range(0, len(text), step)]
    return [w for i, w in enumerate(windows) if i == 0 or len(w) > overlap]
```

The filter on the last line is not cosmetic. Stepping by `size - overlap` means the final
step can land inside the previous window's overlap region and emit a tail that is entirely
contained in its predecessor. Concretely with size 1000 and overlap 200: window *i* covers
`[800i, 800i+1000)`; a final window at `800i` of length ≤ 200 covers `[800i, 800i+200)`,
which the previous window already covers in full.

Without the filter you get a duplicate chunk at the end of roughly every long section:
same text, different id, its own vector. It costs an embedding call, it occupies a
results slot, and it makes chunk counts non-obvious. Nothing errors. This is a small
instance of the pattern that runs through the whole system — the failure is a slightly
worse result, not a crash.

`i == 0` guards the case of text shorter than `overlap`, which must still produce one
chunk.

### 3.5 Embedding — `embedding.py`

**Input:** `list[str]`. **Output:** `list[list[float]]`, one 1536-float vector per input,
**in input order**.

An **embedding** is a fixed-length vector of floats that represents a piece of text's
meaning, such that texts about similar things land close together. Anthropic does not
serve an embedding model, so this half of the system talks to OpenAI while the rest of the
project does not.

Two decisions.

**Batching, not concurrency.** 128 inputs per request, in a sequential loop. One HTTP call
carrying a list, well inside the endpoint's per-call token ceiling. 284 chunks is three
requests. The alternative — concurrent requests with a thread pool — would cut a handful
of sequential round trips to one wall-clock round trip, and buys a rate-limiter, an ordering
problem, and partial-failure semantics in exchange. For a job that runs when the corpus
changes, that trade is clearly wrong. Note this is worth re-deciding at a different scale;
see section 5.

**Retries at the SDK layer.** `OpenAI(max_retries=3)` applies exponential backoff for
429s, 5xx, and connection errors. Hand-rolling this is the classic place to get backoff
wrong and turn a transient rate limit into a thundering retry storm. The client is
`@cache`d so a process holds one connection pool rather than one per call.

Any `OpenAIError` becomes `EmbeddingUnavailable` at the module boundary — callers depend
on this project's error vocabulary, not the vendor's, which is what makes the provider
swappable.

#### The response reordering — the highest-consequence three lines in the file

```python
# The response is not documented to arrive in input order and carries an
# explicit index per item. Zipping against the inputs would misattribute
# every vector — all of them valid, all of them on the wrong text.
return [item.embedding for item in sorted(response.data, key=lambda i: i.index)]
```

Every item in the response carries an explicit `index` field. That field exists precisely
because the response is not contractually ordered.

The obvious implementation is `[item.embedding for item in response.data]`, or
`zip(texts, response.data)`. Suppose the API returns a batch of 128 in a different order —
today, under load, or after a backend change. Every vector in that batch is attached to
the wrong chunk. Consider what you would observe:

- The indexing run completes with no error.
- The index file has exactly the right number of entries.
- Every vector is a valid, well-formed, unit-length 1536-float embedding of a real piece
  of regulation.
- Every search returns five results, with plausible scores in a plausible range, sorted
  descending.
- The results are text about topics unrelated to the question, with correct-looking
  citations attached.

You would debug your chunker. You would debug your query. You would try a different
embedding model. There is no signal anywhere in the system that points at the batch
loop, because nothing about the data is malformed — only the *correspondence* between text
and vector is broken, and no schema encodes a correspondence.

Sorting by `index` is three characters of Python. Not sorting is a bug that could cost a
week and would be indistinguishable from "retrieval just doesn't work well on legal text."

**The transferable rule: whenever an API returns a collection that corresponds
positionally to a collection you sent, find the correlation identifier in the response and
use it. If there isn't one, treat that as a defect in the API and build one — send inputs
with a key and match on the key.** Positional correspondence across a network boundary is
an assumption, and this is the assumption class that produces the worst debugging
experiences in retrieval systems.

`index.py` closes the same loop from the other side with `zip(chunks, vectors,
strict=True)`, which raises if the counts ever diverge rather than silently truncating to
the shorter list — Python's `zip` default, and another silent-loss default worth knowing.

### 3.6 Similarity and normalization — `similarity.py`

**Cosine similarity** measures the angle between two vectors and ignores their magnitude:

```python
denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
return 0.0 if denominator == 0.0 else float(np.dot(a, b) / denominator)
```

Why angle and not distance: in an embedding space, magnitude correlates mostly with how
much text was embedded. Euclidean distance would score a long passage and a short one
about the same obligation as dissimilar — which in this corpus means a two-line definition
and the eight-thousand-character section that applies it look unrelated. That is the wrong
answer for every question in the evaluation set.

The zero guard matters because `normalize` can emit a zero vector (from a degenerate
embedding), and a zero vector has no defined angle. Returning 0.0 makes it sort to the
bottom of every query rather than producing a `nan` that propagates through `argsort` and
silently reorders the entire result list.

#### Two implementations of the same measure, on purpose

`cosine_similarity` is **never called by the query path.** `store.search` computes the same
measure as one matrix multiply.

This looks like dead code and it is not. The two exist together because they teach
different things:

- The hot path is `self._matrix @ query_vector`. It is correct and it is fast, and it
  tells a reader nothing about what is being measured. There is no visible angle, no
  norm, no division.
- `cosine_similarity` spells out the formula. Understanding *why* the fast path is
  equivalent is the actual piece of knowledge.

The equivalence: `normalize` scales every vector to unit length **at index time**.

```python
def normalize(vector):
    magnitude = float(np.linalg.norm(array))
    return array.tolist() if magnitude == 0.0 else (array / magnitude).tolist()
```

Once ‖a‖ = ‖b‖ = 1, cosine similarity's denominator is 1, and the whole formula collapses
to the dot product. So a single matrix multiply over the stacked corpus computes exact
cosine similarity for every chunk at once — not an approximation of it.

**That equivalence is asserted, not just claimed.** `normalize` carries a doctest:

```python
>>> left, right = [3.0, 1.0, 0.0], [1.0, 2.0, 2.0]
>>> dot = float(np.dot(normalize(left), normalize(right)))
>>> abs(dot - cosine_similarity(left, right)) < 1e-6
True
```

Run it with `uv run python -m doctest similarity.py`. Three lines, and they are the direct
answer to the reasonable objection "why keep a function nothing calls." The uncalled
function is the **specification** of what the hot path computes, and the doctest is what
makes it a specification rather than a comment that happens to be shaped like code. Delete
`cosine_similarity` and the matrix multiply in `store` has nothing left to be checked
against. Keep it *without* the doctest — which is how it stood until the audit — and the
pairing is decorative: two implementations of one measure sitting beside each other, with
nothing anywhere in the repository verifying that they agree. **A fence that cannot fail
is a comment.** The assertion is what converts the claim into a guarantee, and it belongs
on `normalize` rather than on `cosine_similarity` because `normalize` is the function
whose entire purpose is to license the substitution.

This is the reason `index.py` calls `normalize(vector)` before storing and `search.py`
calls `normalize(embed([query])[0])` before scoring. **Both sides must normalize.** Skip
it on the index side and every score is scaled by an arbitrary per-chunk magnitude, which
systematically favours chunks whose raw embeddings happen to be longer — a ranking bias
with no error attached. Skip it on the query side and every score is scaled by one
constant, which does not change the ranking but does make the printed scores
uninterpretable and breaks any absolute threshold you later add.

Keeping the written-out formula next to the optimized path is a deliberate deviation from
"don't repeat yourself," and it is the right call here because the project's output is
understanding. In a product codebase you would delete it. Know which kind of codebase you
are writing.

### 3.7 The index — `store.py`

One JSONL file. The first line is a provenance header; every subsequent line is one
`EmbeddedChunk`.

#### The provenance header

```python
class IndexHeader(BaseModel):
    snapshot_date: str
    embedding_model: str
    dimensions: int
    chunker: str
    chunker_params: dict[str, int]
    chunk_count: int
    section_count: int
```

An index is a derived artifact, and a derived artifact without its inputs recorded is a
number you cannot reason about. Take this document's own headline figure. "recall@1 was
9/10" is not a result; "recall@1 was 9/10 over 284 chunks from 126 sections of the
2026-08-01 edition, chunked structurally at a 6000-character cap, embedded with
text-embedding-3-small at 1536 dimensions" is a result, because it can be compared to
another one and you can see what changed.

That comparison is the whole of section 1. Set it beside "10/10 over 570 chunks from the
same 126 sections at a 1000-character cap, same model, same dimensions" and the two
differing fields — the chunker and its cap — are the entire space of explanations for the
gap. Without the header you would have two numbers and a memory of how you produced
them.

`evaluate.py` prints the header fields alongside its scores for exactly this reason. If
you take one habit from this codebase into your next project, make it this one: **the
artifact carries the description of how it was made.**

#### `IndexStale` — the check that makes a whole failure class impossible

```python
if header.embedding_model != EMBEDDING_MODEL:
    raise IndexStale(
        f"{path.name} was built with {header.embedding_model!r} but "
        f"queries would be embedded with {EMBEDDING_MODEL!r}; distances "
        f"between two vector spaces are meaningless. Rebuild the index."
    )
```

This is the single most common silent failure in a retrieval pipeline, so it deserves the
full walk-through.

You build an index with `text-embedding-3-small`. Weeks later you change
`EMBEDDING_MODEL` in config — to try a better model, or because someone bumped it in a
refactor. You do not rebuild. You run a query.

The query is embedded by the new model into a 1536-dimensional space. The index holds
vectors from the old model in a *different* 1536-dimensional space. The dot product
between them is arithmetically well-defined. It produces a float. `argsort` orders the
floats. Five results come back with scores that look entirely normal — 0.4, 0.38, 0.37.

The numbers are meaningless. Two embedding models place the same concept in unrelated
directions; there is no reason for the geometry of one space to say anything about the
other. The ranking is close to arbitrary, but arbitrary in a way that looks like a
mediocre retrieval system rather than a broken one. **The shapes match, so nothing can
detect it downstream.** You would conclude your chunking strategy is bad.

The dimension check catches the same class of change in the case where it *would* have
thrown — an actual shape error inside a dot product, several stack frames from the cause —
and turns it into a sentence that names the fix.

The general shape: **when two artifacts must have been produced under the same assumptions
and nothing about their types enforces it, write the assumptions into one and check them
at the join.** Look for these joins in any system you build. They are where the
plausible-wrong-output bugs live.

`IndexStale` also covers the missing-file case, so "you haven't built the index" and "your
index is from a different world" arrive as the same kind of thing: a fixable state, named,
with the command in the message.

#### One chunk per section — the results-list defence

```python
for position in np.argsort(-scores):
    chunk = self.chunks[position].chunk
    if chunk.section_number in seen:
        continue
    seen.add(chunk.section_number)
    results.append(SearchResult(chunk=chunk, score=float(scores[position])))
    if len(results) == top_k:
        break
```

Return the best-scoring chunk of each of the top *k* **sections**, not the top *k*
**chunks**.

Without this, § 1020.320 — split into ten pieces, every one of them about suspicious
activity reporting — can occupy all five slots for a SAR question. All five are relevant.
All five are the same rule. The user learns nothing they would not have learned from the
first, and § 1022.320, the section they actually needed, is pushed off the list by
fragments of its neighbour.

The corpus makes this worse than it sounds, though not for the reason you might guess.
The median section body is 732 characters — one chunk — so most sections cannot crowd
anything. But **8 of the 11 sections in the evaluation set are over the 6000-character cap
and split into several chunks each**, including both SAR sections and § 1010.100, which
alone splits into 52. The questions worth asking are about exactly the sections that
fragment, so the crowding risk lands on the answers that matter rather than on the
harmless majority. A retrieval system that systematically favours long documents is not a
retrieval system.

Note what this is *not*: it is not deduplication of identical text, and it is not a
diversity heuristic tuned on a validation set. It is a statement about the unit of the
answer. **The user asked a question whose answer is a section, so the results list is a
list of sections.** The chunk is an implementation detail of how the section was found.

Getting this right also means the score attached to a result is the score of its *best*
chunk, which is the right summary: a section is as relevant as its most relevant part.

`np.argsort` over the full corpus is O(n log n) where a heap would be O(n log k). At 284
vectors that is microseconds; the simpler code wins.

The empty-corpus guard is in `_scores`, the shared helper both public methods call: a
zero-row matrix multiplies cleanly and both return nothing. An empty candidate set is an
ordinary result, not a bug.

`search` is not the only question you can ask of a ranking, though, and the second one is
what section 4.4 is about. `rank_chunks` returns the top *k* chunks with no collapsing —
the ranking `search` filters — so `evaluate` can measure how many distinct sections the
retrieval actually found. It is a separate method rather than a `collapse=False` flag,
because a flag would make the one-chunk-per-section guarantee depend on an argument:
every caller would have to be read to know whether its results were sections or fragments.
Two questions, two names.

### 3.8 The query path — `search.py`

```python
def embed_query(query: str) -> list[float]:
    return normalize(embed([query])[0])
```

One line, and every piece of it was established above: the same `embed` the index used and
the same `normalize` that makes the dot product exact. `main` hands the result straight to
the store, which supplies the dedupe-and-rank:

```python
results = store.search(embed_query(query), top_k=top_k)
```

There used to be a `search(store, query, *, top_k)` wrapper around that call, and it is
worth knowing why it is gone. When `evaluate.py` was fixed (4.4) it needed *two* rankings
from *one* embedding, which the wrapper could not give it — it embedded and searched in a
single breath. So `evaluate` began calling `store.search` and `store.rank_chunks` itself,
and the wrapper was left with exactly one caller: a one-line pass-through standing between
`main` and the store.

Extracting `embed_query` and deleting the wrapper are the same move made in opposite
directions — the part two callers needed became a function, the part one caller used got
inlined. **What earns `embed_query` its name is not that it is shared; it is that the query
side must normalize exactly as the index side did.** That requirement is the subject of
3.6, it is invisible at the call site, and a named function is where it gets stated once
instead of restated at every place a question is embedded.

`format_result` is worth a sentence because its docstring is honest about its purpose —
"render one result for reading with your own eyes, which is the point." Each result prints
the citation, the score, the chunk id, the as-of date, the source URL, the heading path on
its own line, and 320 characters of body. The chunk id and the heading path are there for
debugging: when a result is wrong you want to know *which* fragment matched and what
context went into its vector, and printing them means you find that out from the same
command that produced the bad result.

The `'(no heading in the embedded text)'` fallback prints for every fixed-size chunk. It is
a small piece of teaching in the output itself: run the two strategies side by side and the
difference between them is visible in the result listing, not just in a recall number.

### 3.9 Measuring it — `questions.py` and `evaluate.py`

Reading results by eye is where the understanding comes from. But a retrieval failure here
looks like five plausible passages of regulatory text, one of which is about the wrong
kind of institution — and eyes stop catching that after the fourth question.

**The questions are hand-written, and each expectation was verified by reading the cached
corpus.** Two decisions in that sentence.

*Hand-written, not generated.* A question generated from a source section inherits that
section's vocabulary. Recall against it is inflated, and a before/after comparison between
two chunking strategies becomes a measure of text matching itself. The whole point of the
evaluation is to detect the entity-ambiguity failure, and a generated question would ask
about "money services businesses described in § 1010.100(ff)" — phrasing that makes the
failure impossible. Real users ask "what's the threshold for a check casher."

*Verified by reading, not by keyword match.* The comment in `questions.py` records three
plausible wrong answers that keyword matching produced on the first pass and that were
dropped after reading the sections:

- § 1010.306 sets an FBAR filing *deadline* rather than saying who files.
- § 1022.380 contains the phrase "money transmitter" inside a registration example rather
  than defining it.
- § 1010.415 covers monetary instruments rather than funds transfers.

Each would have made its question's expectation set more generous, and **a too-generous
expectation set lets a bad retrieval score as a hit.** An evaluation set that is wrong in
this direction is worse than no evaluation set, because it produces a number you trust.

*Expectations are sets, not single citations.* Record retention is stated generally in
§ 1010.430 and again, for customer identification records, in § 1020.220. Scoring against
one "correct" section would count a correct retrieval as a miss and push you to
over-tune. `frozenset` makes the multi-answer case the default shape rather than a special
case.

`evaluate.py` reports four numbers. **recall@5** — did any acceptable section appear in
the top five. **recall@1** — was the *first* result acceptable. **MRR** — the mean
reciprocal rank of the first acceptable section, zero where none appears in the top five.
And **distinct sections in the top 5 chunks**, measured on `rank_chunks` before the
collapse.

recall@1 and MRR were added after the first run against real embeddings, for a reason
worth stating plainly: recall@5 came back **10/10 for both strategies** and could not tell
them apart. A saturated metric is not a good result, it is an exhausted one — it has no
remaining capacity to discriminate between the things you are comparing, and reporting it
alone would have let "both strategies score perfectly" stand in for "this evaluation
cannot distinguish them." recall@1 is the same question with the tolerance removed. MRR is
rank-sensitive where recall@5 is a step function, so a correct answer sliding from first
to third is visible in it and nowhere else. Both are measured on the collapsed list a user
actually sees; at rank 1 the collapsed and raw rankings agree by construction — the
best-scoring chunk overall heads both — so recall@1 is not an artefact of the collapse.

**Adding metrics after seeing a result is a genuine hazard**, and it is one move away from
adding metrics until one of them flatters the answer you wanted. Three things keep it
honest here. Both metrics were specified before they were computed. Neither a question nor
an expectation set was touched — tuning the *set* to move a number is the version of this
that cannot be recovered from. And the metric that moved moved *against* the strategy this
project was built to advocate. A metric added after the fact is trustworthy exactly to the
degree that you would have published it had it gone the other way.

`evaluate` prints the collapsed list, the raw chunk ranking, and the rank of the first hit
for every question, hit or miss, so that no number becomes a substitute for looking. The
diversity metric used to be measured after the collapse, where it could only ever report
5.0; see 4.4.

---

## 4. The traps

Everything in this section is something that was wrong in a way that did not announce
itself. One was found during the build; three were found while writing this document, and
one of those turned out to be two bugs on the same line. All are fixed. They stay here in
full — what was wrong, how it was found, why it stayed hidden — because finding them is
the skill this document exists to transfer, and a fixed bug with its reasoning removed
teaches nothing. Each entry now ends with the fix and why that fix rather than another.

### 4.1 Summary of the fenced-off invariants

Every one of these survived the simplification pass (commit `ee0bfd0`), which removed
about 430 lines of abstraction while keeping chunk output byte-identical. They look like
complexity. They are correctness.

| Invariant | Protects against | How the failure would present |
|---|---|---|
| Sort embedding response by `index` | Response order ≠ input order | Every vector on the wrong text; all data valid; results are coherent text on unrelated topics |
| `IndexStale` on model/dimension mismatch | Querying across an embedding-model change | Well-ordered results computed from meaningless distances; looks like a mediocre retriever |
| `heading_path` separate from `body` | Composed text passing as quoted law | A future verbatim-quote check certifies a phrase this code invented |
| One chunk per section in `search` | Long sections crowding the results list | Five fragments of one rule; the correct section pushed off the list |
| Section count vs. structure tree | A silently-ignored API filter | Index built over all 5,442 sections of Title 31; nothing errors |
| Both chunking strategies retained | Losing the ability to justify the design | You keep the good chunker and lose the reason for it |
| Provenance header | Comparing incomparable runs | Two recall numbers, no way to know what differed |
| `cosine_similarity` beside the dot product | Losing the reason the fast path is exact | The next reader "optimizes" by skipping `normalize` |
| `zip(..., strict=True)` in `index.py` | Chunk/vector count divergence | Silent truncation to the shorter list |
| `_windows` tail filter | A final window inside the previous overlap | A duplicate chunk per long section, occupying a result slot |
| `_INLINE_TAGS` | Italic terms split across lines | Defined terms fragmented in most sentences that matter |
| Label sequence continuity (4.3) | Roman numerals read as top-level letters | Sections split mid-obligation; heading paths assert paragraphs that do not exist |
| Unique locators (4.3) | Two chunks of one paragraph reading alike | The near-duplicates the locator was added to prevent |
| Diversity measured pre-collapse (4.4) | A metric the pipeline guarantees | A number that reads as evidence and can never move |
| Both chunkers testing `body` (4.5) | Two indexes over different corpora | A recall delta that partly measures noise chunks |

### 4.2 The section-ordering bug

**What was wrong.** `_walk_sections` originally walked the XML with an explicit stack:

```python
stack = [(part_element, None, None)]
while stack:
    element, subpart, subpart_heading = stack.pop()
    for child in reversed(list(element)):
        if child.tag == _SECTION_TAG:
            yield subpart, subpart_heading, child
        elif child.tag == _SUBPART_TAG:
            stack.append((child, child.get("N"), ...))
```

`reversed(list(element))` paired with a LIFO `pop()` is the standard idiom for
depth-first traversal in document order — and it is only correct when *everything* goes
through the stack. Here, sections are yielded immediately inside the reversed loop while
containers are pushed. So the double reversal cancels for containers and does not cancel
for leaves.

The observable result, reproduced against the cached corpus:

```
buggy:  1010.100, 1010.230, 1010.220, 1010.210, 1010.205, 1010.200, 1010.380, …
fixed:  1010.100, 1010.200, 1010.205, 1010.210, 1010.220, 1010.230, 1010.300, …
```

Subparts in document order; sections reversed within each subpart. The function's own
docstring said "in document order."

**How it was found.** Not by a test and not by a failure. During the simplification pass
the function was being rewritten from an explicit stack into a recursive generator, and
the two implementations were compared on their output. The rewrite was motivated by
readability; the bug fell out of the comparison.

**Why it survived, and this is the part that matters.** The section-count check against the
structure tree passed the entire time. It compares `len(parsed)` to an expected integer —
the *set* of sections was correct and complete; only their order was wrong, and a count
cannot see order.

Then ask what downstream depended on order:

- Chunk ids are `{section_number}#{index}` where `index` is within a section, so ids were
  unaffected.
- Chunk *content* was unaffected — each section's body is parsed independently.
- Embeddings are per-chunk and order-independent.
- The store sorts by score at query time, so retrieval was unaffected.
- The index file's line order changed. Nothing reads it positionally.

So the bug was real, contradicted the documented contract, and had **no observable effect
on any output the project produces.** It could have sat there for the life of the project.
The day it would have mattered is the day someone added a feature that assumed document
order — "show me the three sections following this one," a prev/next citation walker, a
positional diff between two snapshots — and that feature would have been wrong, subtly,
with the loader looking innocent.

**The lessons, both of them:**

1. **A count check verifies membership, not sequence.** If order is part of your contract,
   assert on order. `parsed == sorted(parsed, key=...)` is one line and would have caught
   this at the first run.
2. **A docstring is a claim, and an unverified claim in a docstring is worse than no
   docstring** — it stops the next reader from checking. The docstring here said "document
   order" and was believed for four commits.

The fix is a recursive generator that yields in document order by construction, which is
also why it is now hard to get wrong: there is no ordering decision left in the code to
make incorrectly.

### 4.3 The paragraph-detection line, which was wrong twice — FIXED

Found while writing this walkthrough, by printing a histogram. Fixed in `chunking.py`;
`check_labels.py` is the acceptance check and it now passes.

```python
_TOP_LEVEL_PARAGRAPH = re.compile(r"^\(([a-z]{1,2})\)\s", re.MULTILINE)
```

The intent, stated in the comment above it: match only the outermost paragraph level,
`(a)` through `(zz)`, because that is where a self-contained obligation begins. That one
line got two independent things wrong.

#### Bug one: roman numerals are letters too

CFR numbering nests as `(a)(2)(i)(A)(1)` — lowercase letters, then arabic numerals, then
**lowercase roman numerals**, then uppercase letters. And `_normalize` puts every block
element on its own line, so a deeply nested paragraph `(a)(2)(ii)` begins a line as
`(ii) …`.

`ii` is two lowercase letters. It matched. So did `i`, `iv`, `v`, `vi`, `ix`, `x`, `xi`,
`xv`, `xx`. But `iii`, `vii`, and `viii` are three letters and did not.

The label histogram over the whole corpus, before the fix:

```
ii: 128   i: 86   iv: 33   v: 21   a: 19   b: 18   c: 18   d: 16 …
```

The two most common "top-level paragraph labels" in the corpus were roman numerals from
the third level of nesting. § 1022.320's true top-level structure is `(a)` through `(g)` —
seven paragraphs. The splitter produced eleven:

```
a(1070), i(411), ii(427), iv(1392), b(1141), c(905), d(1007), ii(2197), e(601), f(237), g(221)
```

Three consequences, none of which raised anything:

1. **Splits happened at the wrong level.** Paragraph (a) — a single coherent obligation —
   was shredded into four pieces at sub-sub-paragraph boundaries. A defined obligation was
   separated from the conditions that qualify it, which is precisely the failure the
   structural chunker was built to prevent.
2. **Splits were inconsistent.** `(i)`, `(ii)`, and `(iv)` split; `(iii)` did not. So
   sub-paragraph (iii) stayed glued to the end of (ii)'s chunk. The chunk boundaries
   followed a rule with no meaning in the document.
3. **The locator was a false statement, and it was not unique.** § 1022.320 produced two
   chunks whose heading path ended `— paragraph (ii)`. That string claims a top-level
   paragraph (ii) exists in this section. It does not. The text is embedded into the
   vector and printed in search results, so the system asserted a structural fact about
   federal regulation that is false. 18 of the 19 sections that split at all had at least
   one repeated label.

#### Bug two: `(b)(1)` has no space after the label

The regex required whitespace after the closing paren. Some CFR paragraphs run the label
straight into their first sub-label:

```
(b)(1) With respect to each certificate of deposit sold or redeemed …
```

`^\(([a-z]{1,2})\)\s` does not match that. Nine top-level paragraphs in this corpus were
invisible to the splitter for this reason, including § 1020.410(b) — which is why that
section's label stream ran `a` … `c` with no `b` in it.

This bug is worth as much attention as the first, because it fails in the opposite
direction and is therefore invisible to the same tests. Bug one produced labels that
should not exist; bug two lost labels that should. A check that only looks for junk
labels sees nothing wrong here — the sequence check in `check_labels.py` catches it
because a run that skips `b` is not `a, b, c, …`.

#### Why neither announced itself

The chunks were still real regulation text. They still carried the correct section, part,
and citation, so retrieval kept landing on the right *section* throughout — which is the
only thing recall@5 or recall@1 can see. The damage was to *which* passage inside the
right section came back, and to the truth of a locator. Both are invisible unless you read
the locator against the source, and neither would have moved a single number in section
1's table.

**How you would find it yourself:** print the histogram. Any time you infer structure with
a regular expression, tabulate what it actually matched across the whole corpus and look
at the distribution before trusting it. Ten seconds of work. The histogram above is
self-evidently wrong the moment you see `ii: 128` above `a: 19` — top-level paragraph (a)
exists in every section that splits, and (ii) cannot possibly be seven times more common.

#### The fix, and the route that did not work

The obvious fix — widen or narrow the character class — cannot work, because **depth is
not a property of the label.** `(ii)` is the third sub-sub-paragraph *and* the 35th
top-level paragraph; § 1010.100 uses it in the second sense and § 1022.320 in the first.
Both are correct. No pattern over a single label can separate them.

This document previously proposed fixing it at the root: preserve the nesting depth from
the eCFR XML in `ecfr.py` rather than inferring it downstream from flattened text. **That
route does not exist.** The XML carries no nesting:

- All 1,694 `<P>` elements across the three parts are flat siblings under their section.
  None of them nests inside another.
- They carry no depth attribute. The attribute-key histogram over every `<P>` in the
  corpus is `{(): 1694, ('class',): 1}` — 1,694 with no attributes at all.
- The `<P>` boundaries do not even align with label boundaries: `(a) General. (1) Every
  money services business …` is one `<P>` holding both `(a)` and `(a)(1)`, while `(a)(2)`
  is a separate one.

So `_normalize` is not discarding structure that `ecfr.py` could have kept. The hierarchy
exists only in the leading text label, in the XML exactly as much as in the flattened
body. The earlier root-cause claim was wrong, and the correction is worth more than the
original claim: **before moving logic upstream to recover "lost" structure, confirm the
upstream actually has it.**

What does settle depth is position in the sequence. Top-level paragraphs run a, b, c, …
z, aa, bb, … zz with no gaps, so a label is top level exactly when it is the one the run
needs next. Everything else is nested text inside whichever paragraph is open:

```python
starts: list[re.Match[str]] = []
expected: str | None = "a"
for match in _LETTERED_PARAGRAPH.finditer(body):
    if match.group(1) == expected:
        starts.append(match)
        expected = _next_label(expected)
```

This resolves the ambiguity by context rather than by shape, which is the only thing that
can. `(i)` following `(h)` is top level; `(i)` inside paragraph (h) is not. `(ii)` in
§ 1010.100, arriving after `(hh)`, is top level; `(ii)` in § 1022.320, arriving while (a)
is open, is not. The regex is now `^\(([a-z]{1,2})\)(?=[\s(])`, which also admits the
`(b)(1)` form, and is deliberately named `_LETTERED_PARAGRAPH` rather than
`_TOP_LEVEL_PARAGRAPH`: it matches lettered labels at *any* depth, and the walk above is
what decides which are top level. The old name asserted something the pattern could not
deliver, which is part of how the bug survived.

**The rejected alternative** was to accept any label later in the alphabet than the
previous one, tolerating gaps. It fails on the case that matters: after `(d)`, a nested
`(i)` is later in the alphabet, so it would be accepted and the original bug would remain
for exactly the sections that trip it.

**What strictness costs.** A section with a genuine gap in its lettered run — a paragraph
repealed and not renumbered — ends the walk early and folds the remainder into the last
paragraph it reached. No section in this corpus has one. `unreached_paragraphs` in
`chunking.py` detects it, and `check_labels.py` fails on it.

Detecting it is harder than it sounds, because **the truncated run a gap leaves behind is
itself a valid sequence.** Given `(a) (b) (d) (e)`, the walk stops at `b` and emits the run
`["a", "b"]` — and `a, b` is perfectly consecutive, so the sequence check can never see the
hole. Nothing about the run is wrong; the run is just short, and a short run is what a
short section looks like.

What does see it is the text left behind: two labels **adjacent in the a…z, aa…zz run**,
here `(d)` followed by `(e)`. Nested roman numerals can never produce that pair, because
they are never adjacent in the top-level run — `(i)` is followed by `(j)`, `(ii)` by
`(jj)`. That asymmetry is the whole trick, and it is what keeps the detector off
legitimate nesting.

The naive version — "does the last paragraph's text contain any further lettered match" —
does not work, and the corpus says so immediately: it flags **66 of the 183 labelled
chunks**, every one a legitimate nested numeral. Any check written against this problem
has to be run against the real corpus before it is believed, for the same reason the
original bug survived: on a first read it looks obviously right.

**The blind spot, stated plainly.** A gap that skips to a *single* trailing label —
`(a) (b) (d)`, with nothing after it — leaves no adjacent pair and is still missed. That
hole is left open deliberately. Closing it would mean judging a lone `(d)` on its own, and
the only way to do that is a set of labels that "look like roman numerals" — which is
exactly the classify-by-shape reasoning this entire section exists to kill. **A narrower
detector with a documented hole beats a wider one built on the premise that already
failed.** Write the limitation into the docstring and move on.

#### The uniqueness half

Fixing the labels left a second problem the histogram exposed: when a single top-level
paragraph is over the cap and gets windowed, every window kept the bare label, so two
chunks of § 1020.220(a) both read `— paragraph (a)`. The locator was true but not unique,
which defeats the entire reason it exists — those two chunks are near-duplicates in the
vector space with identical composed context. Windows are now numbered, `part 1 of 2`,
and the pre-`(a)` piece is located as `preamble` rather than `paragraph (preamble)`,
which was never a paragraph label at all.

#### The acceptance check

`check_labels.py` was written before the fix and now enforces three properties:

- the distinct top-level labels of every section form a consecutive run `a, b, c, …`
- no section's lettered run has a gap the walk stopped at
- no two chunks of one section share a heading path

Before: 18 sections with a repeated label, 19 with an out-of-sequence run. After: zero and
zero, and the histogram reads `a:19 b:19 c:18 d:16 e:15 f:13 g:9 …` — a clean decay,
which is what a real top-level sequence looks like.

**The check had a silent failure of its own.** It reads locators back out of heading paths
with a regex — and that regex reverse-engineered a string format that
`chunking.structural` owns. Change the f-string that builds the locator and the regex
matches nothing, the label map comes back empty, every property holds vacuously over zero
labels, and it prints PASS. **A test that can quietly stop testing is worse than no test,
because it is also a false assurance**, and the property it guards is one nothing else in
the pipeline can check.

The fix is **ownership, not detection.** `_LOCATOR` and `paragraph_label()` now sit in
`chunking.py` directly beside the f-string that composes the locator, so the format and its
inverse are edited in the same three lines by whoever changes either one. Detection was the
alternative — have the check notice it parsed nothing and fail — and it is strictly weaker:
it reports the drift only *after* it has happened, on whatever run someone happens to look
at, whereas co-location makes the two hard to change apart in the first place. The guard is
in as well, because it costs one line and covers drift arriving by a route co-location does
not:

```python
if not labels:
    print("FAIL — no locators parsed; the check cannot see what it grades")
    return 1
```

The general lesson is worth more than the fix. **When two modules must agree on a format,
one of them owns it and the other imports it.** A checker that re-derives what it checks
shares the failure mode of the thing it is checking — and it fails in the direction that
reports success.

### 4.4 The evaluation metric that could not fail — FIXED

Found while writing this walkthrough. Fixed in `store.py` and `evaluate.py`.

`evaluate.py` reported a second metric alongside recall, documented as:

> **distinct sections in top 5** — how much of the list is separate sections rather than
> fragments of one section shouting over the others.

```python
retrieved = [r.chunk.section_number for r in search(store, question)]
distinct_total += len(set(retrieved))
```

`store.search` already collapses results to one chunk per section (3.7). Every element of
`retrieved` therefore had a distinct `section_number` by construction, so
`len(set(retrieved)) == len(retrieved) == 5` for every question over a 117-section corpus.
The metric printed `5.0` and could only ever print `5.0`.

It measured a property that a component upstream of it guarantees. The thing it claimed to
detect — fragment crowding — was made impossible before the measurement ran.

**Why this was worth as much space as a real bug.** A metric that cannot vary is worse
than no metric. It occupied the slot where a real diversity measurement belongs, it
printed a number that reads as evidence, and it would have reported perfect diversity
forever — including on the day someone removed the dedupe from `store.search` as an
"unnecessary" complication and introduced exactly the failure the metric was written to
catch. It was almost certainly written before the dedupe existed, and went vacuous when
the dedupe landed.

**The general trap: when you add a defence, check whether it invalidates the measurement
that motivated it.** Defence and metric are two halves of one thought, and moving one
without the other leaves a number that lies.

**The fix.** Measure on the raw ranking, before the collapse. `InMemoryStore.rank_chunks`
returns the top *k* chunks with no deduplication, and `evaluate` counts distinct sections
in that list.

**Why a separate method rather than `search(..., collapse=False)`.** A flag would make the
one-chunk-per-section guarantee conditional on an argument. Today every caller of `search`
knows, from the method alone, that it will not get five fragments of one section; with a
flag, that invariant is one default away from being off and you have to read each call
site to know what came back. The guarantee is the whole point of `search` — it is what
stops a long section filling the results list — so it stays unconditional. Two questions
get two names. Both share a private `_scores` helper, so the matrix multiply is written
once.

`search()` itself is unchanged, and so is what every existing caller receives.

**Confirming it can move.** With no API quota at the time, the check ran against a
deterministic bag-of-words stub embedder — *not* the real model, and not a
retrieval-quality result. It established only that the metric was no longer constant: 3.0
for `fixed` and 3.7 for `structural`, where the old one reported 5.0 for both.

**The real embeddings have since been run, and the stub was right about direction and
wrong about magnitude.**

| | stub embedder | measured |
|---|---|---|
| `fixed` | 3.0 | **2.6** |
| `structural` | 3.7 | **2.9** |
| gap | 0.7 | **0.3** |

The sign held: `structural` does surface more distinct sections, for the predicted reason
— `fixed` emits more fragments per section, so a long section has more pieces with which
to crowd the list. The size did not hold. The stub overstated both arms and more than
doubled the gap between them, so any threshold set on 3.0-versus-3.7 would have been set
in the wrong place, and "structural finds nearly four distinct sections out of five" was
never true.

That is the right amount of trust to place in a stub, and it generalises: **a stub
embedder can tell you a metric is alive and which way it points; it cannot tell you how
big anything is.** Bag-of-words overlap and a trained embedding model do not fail in the
same places, and a difference between two chunking strategies is a second-order quantity
of exactly the kind where they diverge. Use a stub to prove a measurement is not constant
— which was this one's entire job, and it did it — and re-run on the real model before
quoting a figure to anyone.

### 4.5 The corpus asymmetry between the two chunkers — FIXED

Nine of the 126 sections are `[Reserved]` — placeholder numbers with no text.

`structural` skipped them: `if not section.body.strip(): continue`.

`fixed_size` did not, because it tested the wrong string:

```python
text = f"§ {section.number} {section.heading}\n{section.body}".strip()
if not text:
    continue
```

`text` is never empty when the heading exists, so `[Reserved]` sections produced a chunk
whose entire content was `§ 1010.305 [Reserved]`. Nine such chunks were indexed under the
fixed strategy, all near-identical to each other, all pure noise. The fixed index covered
126 sections; the structural index covered 117.

**Why this mattered more than it looks.** The headline output of this project is a
comparison between the two strategies. Two indexes built over different corpora are not
comparable, and the difference ran in the direction that flatters the conclusion: the
noise chunks sat only in the `fixed` index, so any recall gap between the strategies would
have partly measured nine junk chunks rather than the chunking idea being tested. A
benchmark whose two arms see different data is not a benchmark.

**The fix** is one line — test `section.body.strip()`, the same condition `structural`
tests. Both strategies now cover the same 117 sections.

It is a clean example of a guard that tests a value adjacent to the one it means. The
check intends "does this section have content"; it asked "is this string non-empty" about
a string that had just been built to contain a heading. The lesson generalizes past this
bug: **when two code paths must agree on which inputs to skip, they have to test the same
expression, not two expressions that look equivalent.**

### 4.6 What the header records but does not enforce

`IndexHeader` stores `snapshot_date`, `chunker`, and `chunker_params`. `InMemoryStore.load`
validates **only** `embedding_model` and `dimensions`.

So: change `SNAPSHOT_DATE` in config, do not rebuild, and every result is dated with the
old snapshot from the index while the config claims the new one. The system prints an
as-of date that is truthful about the corpus and inconsistent with its configuration —
which is a lesser failure than a model mismatch (the vectors are still coherent) but is
exactly the class of thing this project treats as unacceptable, since the as-of date is
part of the answer.

Similarly, nothing stops the chunker parameters in `config`/`chunking` from drifting from
the ones that built the index.

This is defensible as drawn: the model/dimension mismatch corrupts *scores*, while a
snapshot mismatch corrupts *metadata*, and only the first is silent in the results
themselves. But the header already carries the field, so extending the check is three
lines. Stated here as an honest gap rather than a design.

### 4.7 Smaller sharp edges

- **`_title_case` uses `str.title()`.** `str.title()` capitalizes after every non-alpha
  character, so `"BANK'S"` becomes `"Bank'S"`. No part heading in this corpus contains an
  apostrophe, so it is latent — but it is embedded text and printed output, so widening
  `PARTS` could surface it.
- **Part headings are title-cased; subpart headings are not.** `"Rules for Banks"` sits
  next to `"Reports Required To Be Made By Banks"` in the same heading path. Cosmetic, but
  both strings go into the vector.
- **`InMemoryStore.load` on an empty file** raises `StopIteration` from `next(handle)`
  rather than `IndexStale`. Only reachable from a truncated write.
- **`evaluate.py` embeds one query per API call**, ten sequential round trips where one
  batched call would do. `embed` already takes a list. Harmless at ten questions;
  the first thing to change at a hundred.
- **`check_labels.py` re-parses the corpus on every run.** `main` is a short sequence of
  named steps — `_labels_by_section`, `_out_of_sequence`, `_gapped`, `_duplicate_paths` —
  and each of them needs the corpus, so it calls `load_sections` and `structural` itself
  rather than reading an index. The gap check needs the section *bodies* as well as the
  emitted chunks, because the text a gap swallows never becomes a chunk of its own and so
  cannot be found by inspecting the output alone. Staying off the index is what keeps the
  whole check runnable with no API key — the reason it could verify 4.3's fix at all — at
  the cost of a few seconds.

### 4.8 What this evaluation cannot show — OPEN

Not a bug and not fixed. This is the standing limitation of the measurement in section 1,
written down so the null result is not read as more than it is.

Ten questions, each naming its own regulated entity, over 117 sections carrying text,
scored at k = 5. Before concluding "structure-aware chunking does not help retrieval,"
be exact about what that set is unable to detect.

**recall@5 is saturated.** Both strategies answer 10 of 10. A metric both arms max out
cannot rank them; the only information left in it is that neither is catastrophically
broken. It stays in the output because a drop below 10/10 would mean something, but it
cannot be the headline, and the run that produced it is the reason recall@1 and MRR now
exist (3.9).

**k = 5 over 117 sections is a wide net.** Five slots from 117 candidates, for questions
whose answers are sections the questions were written to describe, is not a demanding
test. Most of the retrieval budget is spent before the chunker matters.

**Every question uses the regulation's own term for the entity.** "money services
business" and "bank" — the exact strings that appear in the target bodies 36 and 42 times
(section 1). This is the flaw that matters most, because it disables the specific thing
the project set out to test: **a question set that hands over the disambiguating token
cannot measure disambiguation.** The set does not merely fail to find the entity-ambiguity
failure; it is constructed so that the failure cannot arise at the rank that is scored.
Section 1 found the predicted confusion alive at rank 5 under `fixed` and absent under
`structural` — a real difference between the two strategies, on the exact axis the project
was built to test, that every metric here is blind to because rank 1 was already a hit.

**No metric here looks below the first hit.** recall@1, recall@5 and MRR are all settled
the moment an acceptable section appears; nothing scores what occupies the remaining
slots. Section 1 turned up a real, measured difference living entirely in that blind spot
— `fixed` leaves a bank section at rank 5 of the MSB results, `structural` does not — and
the harness reports identical recall@5 for both. **A metric that stops at the first hit
cannot evaluate a results list, only a lookup.** Precision@5 against the expectation sets,
or simply counting off-entity sections in the returned list, would see it. Neither is
implemented, and the gap between "answers the question" and "returns a clean list" is
currently unmeasured.

**The two strategies differ in more than one variable.** `structural` changes chunk
boundaries, *and* prepends the heading path, *and* raises the effective size cap from 1000
to 6000 characters. Section 1's single regression traced to the third of those. No number
here attributes anything to one change. An ablation would — the heading path bolted onto
the fixed chunker, or `structural` re-run at a 1000-character cap — and none has been run.

**Ten questions make the scoreboard coarse.** One flipped rank is a tenth of recall@1 and
0.05 of MRR. The gap this evaluation reports between the strategies *is* one question.
Nothing here separates that from noise, and with n = 10 nothing could.

#### What a harder set would need

*Queries that identify the entity indirectly*, in the words a user brings rather than the
words the regulation uses: "a check casher", "a currency dealer", "a business that wires
money overseas", "a prepaid access provider". None of those is the phrase "money services
business"; each resolves to part 1022 only through the definitions in § 1010.100. That is
the question shape the entity-ambiguity hypothesis was actually about, and the current set
substituted the easy version of it without anyone noticing — which is why the hypothesis
went untested for an entire build while appearing to be the point of the project.

*k = 1 or MRR as the headline*, with recall@5 kept only as a floor.

*Enough questions that one flipped rank is not a tenth of the score*, and a meaningful
share of them adversarial by construction — pairs that differ only in the regulated
entity, where returning the 1020 answer to the 1022 question is the scored failure.

**This is named, not built.** Writing it means reading § 1010.100's definitions and
hand-labelling every question against the corpus to the standard 3.9 sets out, *before*
looking at either ranking — a set written after seeing the output is a description of the
current system rather than a test of it. It is the next piece of work on the evaluation
harness, and it is scoped here rather than done here, because doing it inside the same
change that reported the null result would make the two impossible to tell apart.

---

## 5. Where a reasonable engineer would have chosen differently

Stated honestly, with the trade-off rather than a defence.

**Committing 2.2 MB of cached API responses.** Many reviewers reject generated data in
version control on principle. The counter-argument is in 3.2.1 and it is about
reproducibility, not convenience. The cost is real: the repository carries data that will
be stale the moment the pinned date changes, and a second snapshot doubles it. A defensible
alternative is a `make fetch` step plus a checksum file committed in place of the payload —
you keep verifiability and lose offline operation.

**Almost no unit tests.** There is still no test file. There is now exactly one unit
test, the doctest on `similarity.normalize`, and it is a real one — it pins the single
equivalence the entire query path rests on (3.6). But it covers one identity, and that is
all. `check_labels.py` is a corpus-level acceptance check, not a unit test: it proves the
labels are right for *this* corpus and says nothing about `_next_label` at the `z`/`aa`
boundary. The count check, `IndexStale`, and `strict=True` are runtime assertions doing
work tests would otherwise do. But `_windows`, `_top_level_paragraphs`, and `_serialize`
are pure functions with tricky edge cases and still no coverage — and a five-line test on
`_top_level_paragraphs` would have caught 4.3 the day it was written, years before a
histogram did. If you rebuild this, write those three tests. The honest position is that
`check_labels.py` and the doctest each closed the specific hole they were built for, and
the general one is still open.

**Sequential embedding.** 284 chunks in three requests, sequentially. Correct at this
scale; wrong by an order of magnitude at 50,000 chunks, where the indexing run goes from
seconds to many minutes and concurrency stops being premature.

**Keeping `cosine_similarity` uncalled.** A reviewer will flag it as dead code and they are
not wrong by the usual standard. It stays because the project's product is understanding.
In a service codebase, delete it and put the equivalence in a comment.

**`argsort` over the full corpus.** O(n log n) where `np.argpartition` gives O(n log k).
Irrelevant at 284 vectors, and the simpler code is easier to read. Revisit at 100k.

**Both chunking strategies in the shipped code.** A product would pick the winner and
delete the loser. There is no winner: section 1 measures recall@5 identical, recall@1 and
MRR marginally in favour of `fixed`, and the arguments for `structural` are about the
quality of a correct answer rather than the rate of one. Here the comparison is the
deliverable and both stay — but be clear-eyed that it doubles the index-building cost and
the surface area, and that a reader who does not know why `fixed` exists will eventually
delete it.

**The 6000-character cap was never tuned.** It was picked to keep obligations intact
while sitting well inside the model's 8192-token input limit (3.4.2) — both good reasons,
neither of them about retrieval. Section 1's one regression is a dilution effect from
precisely that cap. The obvious next experiment is `structural` at a smaller cap, which
would keep paragraph boundaries and the heading path while giving up the "a section that
fits should not be split" principle for long sections. It has not been run, and until it
is, the cap is a design choice with one piece of evidence against it and none for it.

**Two providers.** The system talks to OpenAI for embeddings because Anthropic does not
serve an embedding model. That is a hard constraint, not a preference, but it is worth
knowing that it means two API keys and two vendor error vocabularies if a generation layer
is added later.

---

## 6. Reproduce it yourself

Ordered, hardest last. Each is completable from this document alone.

### Exercise 1 — Make the silent failure visible (30 minutes)

The measured results are in section 1. This exercise reproduces them, and its value is in
where your expectations disagree with what comes back. Build both indexes and run the
evaluation over each:

```
uv run --env-file .env index.py fixed
uv run --env-file .env index.py structural
uv run --env-file .env evaluate.py fixed
uv run --env-file .env evaluate.py structural
```

Then run the two SAR questions through `search.py` against each index and read the output
with your own eyes.

Write down: which sections does `fixed` return for the MSB question, and what heading path
does it print?

Now the part that matters. **Before checking, predict how many of § 1022.320's twelve
fixed-size windows contain the phrase "money services business."** Commit to a number, then
count them:

```
uv run python -c "
from ecfr import load_sections
from chunking import fixed_size
ws = [c for c in fixed_size(load_sections()) if c.section_number == '1022.320']
print(sum('money services business' in c.body.lower() for c in ws), 'of', len(ws))"
```

Section 1 of this document got that prediction wrong, and stayed wrong through a build and
an audit, because nobody ran the three lines above. Getting it wrong yourself is the
fastest route to the only lesson in it: an assumption about what a corpus contains is
checkable in seconds, and an unchecked one can sit at the head of a design document
determining what gets built.

Then predict what would happen to `structural`'s recall if you changed only
`Chunk.embed_text` to return `self.body` — and run it to check.

### Exercise 2 — Break each invariant and watch nothing fail (1 hour)

For each, make the change, rebuild if needed, run a query, and write down *how you would
have discovered the bug if you had not been told it was there*.

1. Delete the `sorted(..., key=lambda i: i.index)` in `_embed_batch` and replace it with
   plain iteration. Then simulate a reordered response by shuffling `response.data` before
   returning. Rebuild, query, and describe the output.
2. Remove the `seen` set from `InMemoryStore.search` and query "What is the SAR filing
   threshold for a bank?"
3. Change `EMBEDDING_MODEL` to `"text-embedding-3-large"` and comment out the model check
   in `load`. Do not rebuild. Query. Look at the scores.
4. Remove the section-count check in `load_sections` and change `?part={part}` to
   `?chapter=X`. Report how many sections load and how long it takes to notice.

The deliverable is not the diffs. It is four short paragraphs on detection.

### Exercise 3 — Verify the section-ordering bug for yourself (45 minutes)

Without looking at git history: write a standalone script that reimplements the buggy
`_walk_sections` (the explicit stack with `reversed(list(element))` and `pop()`), run both
implementations against `data/raw/2026-08-01/title-31-part-1010.xml`, and print the first
twelve section numbers from each.

Then answer, from the code alone: why do the *subparts* come out in document order while
the *sections* within them come out reversed? Your explanation has to name the two places
the reversal is applied and say why one cancels and the other does not.

Finally: write the one-line assertion that would have caught this on the first run, and say
where in `load_sections` it belongs.

### Exercise 4 — Rebuild the paragraph splitter from the bug report (2–3 hours)

Revert `_top_level_paragraphs`, `_next_label`, and `_LETTERED_PARAGRAPH` to the single
regex `^\(([a-z]{1,2})\)\s` and delete `check_labels.py`. Then, from section 4.3's
description of the *symptoms* only — do not re-read the fix — rebuild both.

Write the check first. It has to print the label histogram and fail on two conditions:
a section whose distinct top-level labels are not a consecutive run from `a`, and two
chunks of one section sharing a heading path. Against the reverted code it should report
18 sections with a repeated label and 19 with an out-of-sequence run.

Then make it pass. Your splitter must classify `(i)` as top level after `(h)` and as
nested inside paragraph (h); treat `(iii)`, `(vii)`, `(viii)` consistently with `(ii)` and
`(iv)`; find § 1020.410(b), which is written `(b)(1)` with no space; and give § 1020.320
and § 1022.320 exactly seven chunks each.

Finally, answer the question this document got wrong the first time: could this have been
fixed in `ecfr.py` by preserving the XML's paragraph nesting instead? Establish the answer
from the XML yourself — count the `<P>` elements under a section, look at their attributes
and their nesting — before reading the end of 4.3.

### Exercise 5 — Show the diversity metric is load-bearing (1 hour)

`rank_chunks` and the metric that uses it are already written (4.4). This exercise is
about proving the metric now does what the old one could not.

First, without an API key: write a deterministic stub embedder — a bag of words hashed
into a fixed-width vector, normalized — and build both indexes in memory with it. This is
the harness the fix was verified with, and building it yourself is the point: you cannot
check a retrieval metric without *some* embedder, and a stub you control is better than a
real one you cannot afford to run repeatedly.

Confirm three things. The new metric differs between `fixed` and `structural`. The old
metric — distinct sections among `search`'s output — is exactly 5.0 for both. And when you
delete the `seen` set from `store.search`, the *old* metric collapses toward 1.0 while the
new one does not move at all, because it never depended on the collapse.

That last result is the whole argument: the old metric was measuring the dedupe, not the
chunking. Write down, in two sentences, why a metric that tracks a guarantee you already
enforce is worse than printing nothing.

Finally, compare your stub's two numbers against the measured ones in 4.4 — 2.6 and 2.9.
The stub used when this fix landed reported 3.0 and 3.7: right about which strategy is
higher, wrong about both values and more than double on the gap. Note how far yours lands,
and treat that distance as the standing discount on every number a stub embedder gives
you.

### Exercise 6 — Rebuild the loader from a blank file (4–6 hours)

Delete `ecfr.py`. Do not look at it, and do not look at git history. From this document and
the eCFR API alone, write a module exposing `load_sections() -> list[Section]` against
`models.Section` unchanged.

It must: fetch and cache through disk; verify the parsed section count against the
structure tree; serialize XML preserving block structure, inline elements, and table rows;
carry subpart headings down through arbitrary `DIV` nesting; yield sections in document
order; and raise `EcfrError` at every boundary.

Acceptance: 126 sections (117 of them with text), and `structural(load_sections())`
produces 284 chunks whose ids, bodies, and heading paths are byte-identical to the ones
your original produces, with `check_labels.py` passing. Save a copy of the current output
before you delete anything.

Expect to get the XML serialization wrong first. Note which of the four decisions in
section 3.2 you had to rediscover rather than recall — that is the list of things you did
not actually learn from reading.

### Exercise 7 — Extend it to a component that does not exist yet (a day)

Add a generation layer: given a question, retrieve, then produce a prose answer in which
**every factual claim is followed by a verbatim quote from a retrieved chunk's `body` and
its citation**, with a programmatic check that each quoted span appears in the `body` it is
attributed to.

This is where the `heading_path`/`body` split (3.3) stops being theoretical, and you should
be able to say precisely why the check would be worthless if `Chunk` had a single `text`
field.

Then handle the case this system currently cannot: the question "what is the SAR threshold
for a money services business" whose correct answer requires *both* thresholds in
§ 1022.320 — the $2,000 general duty and the $5,000 clearance-record rule for issuers of
money orders and traveler's checks from 3.4.1 — which live in different top-level
paragraphs and therefore different chunks. Decide whether that
is a retrieval problem, a chunking problem, or a generation problem, and defend the answer.
