# Earned abstraction pass

Status: to-do, not scheduled. Delete this file when the pass has landed.

## Context

The repository coins terms for its own mechanisms — for example:

- mechanistic guarantee footprint
- authority and discovery layering
- control-artifact assurance spectrum
- governed delivery cardinality latency
- instruction provenance feedback loop

Each is meaningful after explanation, but each raises entry cost. A reader
who does not yet hold the mechanism sees ontology before evidence, and has no
way to tell a load-bearing term from an unnecessary one. One reviewer reads
that as sophistication; another reads it as invented vocabulary. The repo
cannot control which reading it gets, so it should make the question moot.

End state: every coined abstraction in normative or explanatory prose is
paired, at its first use in a document, with one concrete failure it prevents
and one concrete implementation that embodies it (a path, a command, a hook
name, or a literal example). A reader who skips the term still gets the
mechanism; a reader who wants the term finds it earned by the example.

## Rule to apply

At the first use of a coined term in a document, the same paragraph or the
immediately following one must contain:

1. **The failure it prevents** — a specific thing that goes wrong without the
   mechanism, stated concretely enough to be recognized ("the hook fires but
   the manifest cites a source no reader can open").
2. **The implementation** — a repo-relative path, script, config key, or
   command that a reader can open to see the mechanism as code.

A term that cannot be paired with both is a candidate for deletion or
replacement with the plain description. That outcome is a success of the
pass, not a failure to complete it.

## Candidate surfaces

Sweep in this order; the earlier surfaces carry the highest entry cost.

| Surface | Why first |
| --- | --- |
| `README.md` | First contact; abstraction here is unearned by definition |
| `docs/architecture/*.md` (including `authority-and-discovery-layering.md`, `control-artifact-assurance-spectrum.md`) | Titles are coined terms; check each opens with the failure and a path |
| `docs/diagrams/README.md`, `platform/agent-control-plane/docs/diagrams/README.md` | Diagram captions name mechanisms without pointing at code |
| `docs/glossary.md` | Every entry should carry a failure and a path, or be dropped |
| `platform/agent-control-plane/agent-assets/instructions/*.md` | Normative prose; agents pay the entry cost every session |
| `platform/agent-control-plane/agent-assets/skills/*/SKILL.md` | Same, per invocation |
| `docs/architecture/adr/*.md` | Lower priority — ADRs may coin terms that later docs earn |

Two of the five example terms ("governed delivery cardinality latency",
"instruction provenance feedback loop") have no hit in tracked markdown at
the time of writing; they came from external prose about the repo. Confirm
during the pass whether they are still in use before treating them as in
scope.

## How to verify

For each edited document, a reader unfamiliar with the repo should be able to
answer, for each coined term, "what breaks without this?" and "where is it?"
from the document alone. If either answer requires a second document, the
pairing is not complete.

Mechanical check to consider (optional, not a prerequisite): a script that
lists glossary terms and reports documents where a term appears with no
repo-relative path within N lines of its first occurrence. Useful as a
regression guard after the pass, not as the pass itself.

## Out of scope

- Renaming terms wholesale. The pass pairs; it does not re-coin.
- Rewriting ADR bodies. ADRs record a decision at a point in time.
- Evidence files under `evidence/`. They are dated observations, not prose a
  newcomer reads first.
