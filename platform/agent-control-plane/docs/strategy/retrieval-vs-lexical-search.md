# Retrieval strategy for cached provider documentation

This repository caches provider documentation locally (see
[Local Documentation and Artifact Mirrors](../local-doc-mirrors.md)) and
retrieves from it using plain lexical search — `grep`/`sed` against a flat
cached file — rather than an embedding-based RAG pipeline. This note records
why, and what would change the answer.

## The question

The provider-docs mirror (`provider_docs_session_start.py`) caches each
runtime's full documentation manual to a local file with a 24-hour TTL. An
agent then greps that file on demand instead of loading it wholesale into
context. Given that a frontier-model manual seems like an obviously
high-value document, is it worth adding a real embedding-based RAG layer —
chunk, embed, vector-search — in front of it?

## Why lexical search, not RAG, fits this specific corpus

RAG is a bet that pays off when two conditions both hold: the corpus is
large/heterogeneous enough that semantic recall meaningfully beats literal
string matching, and the corpus is stable enough that the cost of building
an embedding index amortizes across many queries before it goes stale.

The provider-docs mirror fails the stability condition specifically:

- It is a single external document, wholesale-replaced on every refresh
  (default TTL 24 hours, `DEFAULT_TTL_SECONDS` in
  `provider_docs_session_start.py`).
- An embedding index over it would need to be rebuilt on essentially the
  same cadence, inverting RAG's normal trade — "expensive preprocessing
  once, cheap querying many times" becomes "expensive preprocessing every
  refresh, for a handful of queries per session."
- The document is already well-structured (headed sections) and uses
  precise, mostly literal vocabulary (flag names, event names, file names),
  which is exactly the case plain lexical search already handles well.

So document *importance* is not the deciding variable — query *shape* and
corpus *stability* are. A single-file, frequently-regenerated, technical
manual is a poor RAG candidate even though it is a high-value document.

## Where lexical search actually failed, and the real fix

An earlier session's retrieval against this same cached manual was
inefficient, but not because lexical search is the wrong mechanism — because
the individual `grep` calls were poorly scoped. The pattern used was a
six-way alternation of guessed synonyms (`"preserves\|compacts\|summarize
conversation\|..."`) followed by `head -20`, which returned ~6.8 KB of
unrelated paragraphs to answer a question with a one-sentence answer. A
second call repeated the mistake, adding a 40-line `sed` range on top of
another wide alternation grep.

The fix is not a different mechanism — it is the same two-call shape
(grep-to-locate, then read-a-window-around-it), scoped tightly: one specific
phrase instead of six guessed alternatives, and a ~10-line window instead of
40. Same round-trip count, same single-turn feel for the user, a fraction of
the context tokens. This is a query-discipline problem, not a
retrieval-architecture problem.

## When embedding-based RAG would earn its keep here

The corpus profile where RAG wins is the opposite of the provider-docs
mirror: large, growing, multi-document, multi-author, with fuzzy/paraphrased
queries rather than known vocabulary. Candidates in this repository closer
to that profile:

- A private `engineering-knowledge-base/` overlay, if mounted, accumulating
  heterogeneous notes over time.
- `evidence/experiments/` writeups, which grow across many authors and
  sessions with inconsistent phrasing.

These are also better candidates for the "pluggable into IDEs" framing this
question was raised under — a stable local index is worth shipping as a
portable artifact in a way a 24-hour-TTL scratch cache never will be.

## Takeaway

Do not add embedding-based RAG in front of the provider-docs mirror. Improve
query discipline in the existing `grep`/`sed` retrieval instead — narrow
patterns, small read windows. Revisit RAG only for corpora that are large,
multi-document, and slow-changing relative to query volume.
