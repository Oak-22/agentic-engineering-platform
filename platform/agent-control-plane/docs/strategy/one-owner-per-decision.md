# One owner per decision, not one function per similar code

## Purpose

Name the rule for when duplicated-looking code should be consolidated, and
the sharper failure it prevents: not repetition, but **silent disagreement**
between copies that were once identical.

This generalizes what
[native-provider-state-ports.md](native-provider-state-ports.md) argues for
provider state and
[session-transcript-reader.md](session-transcript-reader.md) argues for
transcript readers. Both say the same thing about their own domain; this note
states it once, domain-free.

## The rule

Consolidate when several implementations encode **one decision**. Leave them
apart when they merely resemble each other.

The test is not "is this code similar?" but **"would these have to change
together?"** If a change to the underlying convention forces edits in all of
them, they are one decision wearing several names. If they could each evolve
for their own reasons, they are separate concerns that happen to rhyme, and
merging them manufactures coupling that will be painful to undo.

Variation between the copies is not evidence against consolidation. Variation
is usually a **parameter** of the shared decision, and belongs in a
declarative spec rather than in divergent implementations.

## The failure this prevents

The cost of N copies is not N× the lines. It is that the copies **drift**,
and nothing reports it.

A fix applied to one copy does not reach the others. Nobody decides the
copies should differ; the difference just accumulates, one reasonable local
edit at a time. Later, the difference reads as intent — a future maintainer
finds two implementations disagreeing and has no way to tell whether that is
a considered decision or an unrepaired oversight.

Type checkers do not catch this. Tests do not catch it, because each copy's
tests assert that copy's behavior. The divergence is invisible precisely
where it matters.

## Worked instance: this repository's local-store resolution

Four mechanisms independently answered "where does machine-local state live,
and how is it exposed back into the repo": `instruction_manifest_hook.py`,
`resolve_capture_root.py`, `render_session_snapshot.py`, and
`archive_artifact_publish.py`. Each computed `$XDG_DATA_HOME/aep` itself.
Three of the four also wrote near-identical `.local-mirrors/<name>` symlink
helpers under three different names.

They had already drifted:

- Only the evidence-store copy guards symlink creation with
  `except FileExistsError`. The others race.
- Only the evidence-store copy creates its root `mode=0o700`. The others
  inherit the default umask.

Nobody chose to make the show-me capture cache more permissive than the
instruction-evidence ledger. It happened because a hardening fix landed in
one copy and never reached the rest.

The variation that *was* deliberate — the evidence store keys by a hash of
the git remote so one repo cloned twice shares a store, while the others key
by directory name — is exactly the kind of difference that belongs in a spec
field (`scope: "slug" | "repo-hash"`), not in a separate implementation.

Consolidation target: `scripts/local_store.py`.

## Applying it

When you notice similar-looking implementations, ask in order:

1. **Do they encode one decision?** If a change to the convention would force
   edits in all of them — consolidate. If not, stop here.
2. **Have they already drifted?** Diff them. Any difference nobody can
   justify is the argument, and it is stronger than the tidiness argument.
3. **Is the remaining variation parameterizable?** Express it as declarative
   spec fields. If some variation resists that — the evidence store's
   index-file writing, for instance — it was never part of the shared
   decision and stays with its owner.
4. **Can the migration preserve every caller's interface?** Keep the existing
   public names as thin wrappers. A consolidation that also churns call sites
   mixes two risks and makes rollback harder.

## Counter-case

Do not consolidate on resemblance alone. Two validators with the same
control flow over unrelated schemas, two retry loops with different failure
semantics, two formatters for different audiences — these look alike and
answer different questions. Merging them creates a shared abstraction that
must grow a flag every time either side changes, and the flags eventually
outnumber the shared logic.

The asymmetry is worth stating plainly: **premature consolidation is harder
to reverse than tolerated duplication.** Duplication is visible and can be
merged later. A wrong abstraction hides the fact that two things were ever
separate, and every caller has to be re-litigated to split it. When genuinely
unsure, leave them apart and revisit when the third instance appears — by
then the shared decision, if there is one, is usually obvious.
