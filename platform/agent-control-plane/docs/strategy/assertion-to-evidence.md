# Assertion outrunning evidence

Standing as of 2026-09-14: in use; too early to call. Five instances
recorded, all found in one session, all after the countermeasures below had
landed. Counts and per-countermeasure tallies live in the
[ledger](../../../../evidence/assertion-to-evidence/ledger.md); this line is
the only status in this note.

## Purpose

Name the failure that several of this repository's mechanisms were built
against without anyone having stated it once: an artifact asserts more than
has been shown, and the gap is invisible to review because the artifact has
the correct shape.

## Two tensions, both live

**Over-engineering** is the tension between a programmer's taste for elegance
and the finite resources to build. It is not a past problem. With agents in
the loop the resource side of the tension collapsed, so the failure is now
cheaper to commit, and it is committed more often. The word still describes
it exactly.

**Assertion outrunning evidence** is a different tension: between how cheaply
a claim can be produced and how expensively it can be checked. A plan can
include a verification step in the shape of a verification step. A README can
describe a feedback loop the diagram draws dotted. An instruction can route to
a document that does not exist. Each of these costs a sentence to produce and
a real investigation to falsify, and each passes review because review reads
shape.

The two are distinct because the first was chosen and the second was not.
This repository's excess mechanism — the registry, the layer model — was
argued for and recorded as deliberate. Its unbacked assertions were never
chosen by anyone; they arrived in otherwise correct work.

## Two directions of drift

The ratio between what an artifact asserts and what it has been shown to do
can fail in either direction, and the remedies differ.

| Evidence… | Remedy shape | Countermeasures in this repository |
| --- | --- | --- |
| never existed | pair the claim with its check at write time | evidence labels in the prompt-instruction manifest (`Observed` / `Declared` / `Read during turn`); falsifiable plan units in the traceable-change template; negative verification before a target state counts as active (ADR-0005) |
| existed and expired | place the claim where its decay rate is visible; delete on completion | the decay-rate convention in `artifact-formatting.md`; the `future/` delete-on-completion rule; dated observations under `evidence/` |

The earned-abstraction rule (pair every coined term with one failure it
prevents and one path that implements it) is the same remedy applied to
vocabulary, and belongs on the first row.

## Over-assertion has a tense

Over-assertion in the present tense claims a capability that has not been
shown: "telemetry feeds back into the control plane." Over-hedging is the
same claim in the future tense, wrapped in an accurate present-tense
disclaimer: "currently X does not do Y; see Z for future reference." The
disclaimer is true when written and expires when Y ships. The pointer is a
promise with no owner, and if Y never ships it dangles. The honest half
licenses the speculative half through review.

Agents produce this shape by default, as a guard against claiming what does
not exist, and nothing in their default behavior sweeps it up afterwards. So
compliance with "state status once, at the top" requires an active pass,
not restraint at write time. This is the generative cause behind the
*expired* row above.

The code-side analogue is YAGNI: do not build for a predicted need. The
prose-side rule is its cousin — **you aren't gonna update it** — and it
removes both tenses at once. Describe what is. Put the one status line where
it will be edited when the state changes. Leave the future to a plan that is
deleted when the work lands.

## Why the countermeasures are evidence, not just remedies

They predate the recorded instances. The evidence labels landed 2026-07-30
and the plan template 2026-08-18; the five ledger entries were found on
2026-09-14, one of them inside a plan written under that template. A failure
that recurs after its countermeasure has been built is a standing pressure,
not an education gap. If it were the latter, the countermeasures would have
worked.

The cleanest single datum is the `future/` directory: its rule said delete
on completion, six files were added between 2026-08-06 and 2026-09-05, and
git history shows zero deletions before 2026-09-14. The rule and the
measurement come from the same artifact, so the observation needs no
interpretation.

## What would change this note

- The ledger stops growing for a sustained period while the repository keeps
  changing: the countermeasures are working and the status line says so.
- The ledger keeps growing at a steady rate: the countermeasures are
  insufficient and the next step is to identify which direction of drift
  dominates and strengthen that row.
- Instances appear that fit neither direction: the two-row model is wrong
  and needs a third row or a different axis.

## Related

- [`evidence/assertion-to-evidence/`](../../../../evidence/assertion-to-evidence/)
  — the dated ledger.
- [`future/earned-abstraction-pass.md`](../../../../future/earned-abstraction-pass.md)
  — the vocabulary-side pass.
- [`future/close-the-feedback-loop.md`](../../../../future/close-the-feedback-loop.md)
  — resolves ledger instance 2.
- [`future/traceable-change-plan-template.md`](../../../../future/traceable-change-plan-template.md)
  — states the reading-speed argument this note generalizes.
