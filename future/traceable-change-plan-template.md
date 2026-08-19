# Traceable Change Plan Template

A template for planning a change large enough that a reader cannot hold all of
it at once. Not yet installed as a skill; see *Promotion* below.

## Why this exists

A plan is normally read once, quickly, before work starts. If its units cannot
each be checked in isolation, the reader has no way to verify it in that pass —
so they approve it on trust, and the change proceeds on an assessment nobody
actually made.

The failure this resists is not incorrectness. It is correctness that outruns
review: work that is fine, that passes its checks, and that no human ever
reconstructed. In math research, formal verification shows the shape of this already — machine-
checked proofs accumulate faster than they are read, so a body of results is
known to be true and understood by no one. A plan that only a machine can
follow does the same thing on a smaller scale in developer workloads.

The countermeasure is not more detail. It is making each unit *falsifiable* in
the reading: every claim paired with the specific way a reader could show it
false. Review then becomes verification rather than assent, and stays possible
at reading speed.

## Structure

Open with **Context**: the problem, what is untrue today, and the end state.
State the outcome as a condition that will hold, not as a list of activities.

Then **How to read this plan** — name the fields and the claim that each unit
is independently reviewable and separately revertible.

Then one section per unit. Order units by dependency; a unit that requires
another must say so. Each unit states exactly four fields, in this order:

**Touches** — every path the unit adds or changes. Exact paths, no globs. If
this list is long, the unit is too big; split it.

**Mechanism** — how the change is made, including the constraint that forced
the approach. Name the existing function, pattern, or file being reused. If an
obvious alternative was rejected, say why here, in one sentence.

**Claim** — one sentence that becomes true, and was false before. Not a summary
of the work. If the claim restates the mechanism, the unit has no stated
purpose and the reader cannot tell whether it succeeded.

**Trace check** — how a reader confirms the claim without trusting this
document. Prefer a command with an expected result. Where the check is a
falsification — break something specific, watch a check fail — say exactly what
to break and what must happen. A unit whose check is "review the code" has no
check.

Close with **Verification** (the end-to-end sequence, as runnable commands) and
**Risks** (what stays true after the change that someone will later trip on).

## Rules

- One claim per unit. Two claims means two units.
- Every claim gets a check that can fail. If you cannot state the failure, you
  do not yet know what the unit is for.
- Name real paths and real functions. A plan that could describe any repository
  describes none.
- Write no conditional or deferred language. "Once implemented", "in future",
  "when needed" mean the unit is not ready to be planned. Cut it or finish it.
- State a constraint where it first bites, not in a preamble. Constraints
  discovered during planning belong in the Mechanism of the unit they shape.
- Prefer the check a skeptic would run over the check the author would run.

## Promotion

To make this a skill, add a package under
`platform/agent-control-plane/agent-assets/skills/<name>/` with a `SKILL.md`,
**and** its entry in `agent-assets/skills/skills_registry.json` in the same
change. `scripts/validate_asset_registries.py` requires every directory under
`skills/` to have a registry entry and every binding to be a resolving symlink,
so a package added without its registration fails validation immediately.

A worked example of this structure, including its falsification checks, is the
plan that produced the instruction-evidence contract enforcement in
`platform/agent-control-plane/contracts/`.
