---
name: plan-traceable-change
description: Write a plan for a change too large for a reader to verify in one pass, structured so every unit is independently reviewable and separately revertible. Use when asked to plan a large or complex change, when a change spans several units that each need individual verification, or when shaping deferred intent for future/. Do not use for a single small edit a reviewer can already hold and check in one pass.
---

# Plan Traceable Change

## Why this exists

A plan is normally read once, quickly, before work starts. If its units
cannot each be checked in isolation, the reader has no way to verify it in
that pass — so they approve it on trust, and the change proceeds on an
assessment nobody actually made.

The failure this resists is not incorrectness. It is correctness that
outruns review: work that is fine, that passes its checks, and that no
human ever reconstructed. The countermeasure is not more detail. It is
making each unit *falsifiable* in the reading: every claim paired with the
specific way a reader could show it false. Review then becomes verification
rather than assent, and stays possible at reading speed.

## Structure

Open with a one-line **Status** directly under the title: the plan's state
and what ends it, stated once so a status change is one edit.

Then **Context**: the problem, what is untrue today, and the end state.
State the outcome as a condition that will hold, not as a list of
activities.

Then **How to read this plan** — name the fields and the claim that each
unit is independently reviewable and separately revertible.

Then one section per unit. Order units by dependency; a unit that requires
another must say so. Each unit states exactly four fields, in this order:

**Touches** — every path the unit adds or changes. Exact paths, no globs.
If this list is long, the unit is too big; split it.

**Mechanism** — how the change is made, including the constraint that
forced the approach. Name the existing function, pattern, or file being
reused. If an obvious alternative was rejected, say why here, in one
sentence.

**Claim** — one sentence that becomes true, and was false before. Not a
summary of the work. If the claim restates the mechanism, the unit has no
stated purpose and the reader cannot tell whether it succeeded.

**Trace check** — how a reader confirms the claim without trusting this
document. Prefer a command with an expected result. Where the check is a
falsification — break something specific, watch a check fail — say exactly
what to break and what must happen. A unit whose check is "review the
code" has no check.

Close with **Verification** (the end-to-end sequence, as runnable
commands) and **Risks** (what stays true after the change that someone
will later trip on).

## Rules

- One claim per unit. Two claims means two units.
- Every claim gets a check that can fail. If you cannot state the failure,
  you do not yet know what the unit is for.
- Name real paths and real functions. A plan that could describe any
  repository describes none.
- Write no conditional or deferred language. "Once implemented", "in
  future", "when needed" mean the unit is not ready to be planned. Cut it
  or finish it.
- State a constraint where it first bites, not in a preamble. Constraints
  discovered during planning belong in the Mechanism of the unit they
  shape.
- Prefer the check a skeptic would run over the check the author would
  run.

## Worked examples

`future/` holds plans written to this structure, including their
falsification checks — for example `github-surface-boundary-drift-plan.md`,
`workbench-rest-state.md`, and `copilot-dispute-reply-operation.md`. Read
one before writing a new plan from scratch.

## Where the plan lives

A plan produced with this skill for repository-coupled, not-yet-activated
intent belongs in `future/`, per
[ADR-0007](../../../../../docs/architecture/adr/0007-define-the-lifecycle-of-deferred-intent-in-future.md).
Once the plan is activated as tracked work, the `future/` file remains its
scope brief until the delivery pull request merges, at which point it is
deleted, its durable content is promoted into canonical documentation, or
its unrealized residue is split into a new bounded `future/` file — the
three terminal dispositions ADR-0007 defines.
