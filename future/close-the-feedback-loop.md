# Close the feedback loop operationally

Status: to-do, not scheduled. Terminal disposition: split. Outcome B landed
(AEPI-165, `README.md` "Platform Model" and its diagram caption now describe
the return arcs as a maintainer-read, PR-mediated path). This file now scopes
outcome A only. Delete it when an accepted ADR lands.

## Context

`README.md` used to describe the platform as a feedback loop without saying
how the loop closes: the Agent Control Plane governs execution, Inference
Telemetry observes it, Developer Learning converts validated signals into
reusable improvements, and "telemetry findings and validated learning feed
back into the Agent Control Plane." The platform diagram draws the forward
arcs solid and the return arcs dotted.

The dotted arcs were honest — the return path is not built — but the prose
did not say so. AEPI-165 fixed that: the README now states the return path is
a maintainer reading telemetry and learning artifacts and proposing an
instruction change through the ordinary pull-request lifecycle, and that an
automated return path is not built.

What remains open is whether to build that automated path. A reader who
expects an automated close asks six questions the repository does not answer
in any tracked artifact:

1. What exact signal triggers a proposed control change?
2. Is that change applied automatically or human-approved?
3. How is causality distinguished from correlation? (Did the instruction
   improve the outcome, or did the task mix change?)
4. How is a harmful learned rule rolled back?
5. How is overfitting to one developer prevented?
6. How does the system know a newly reinforced instruction improved outcomes?

## What exists today

Verified at the time of writing by reading the component READMEs and
`docs/architecture/`:

- The forward path is real. Instruction-load events are emitted per prompt
  (`.local-mirrors/instruction-evidence/`), the manifest hook cites them, and
  telemetry consumes the control plane's shared port rather than a copy.
- The return path is human-mediated, and `README.md` now says so (AEPI-165).
  A developer reads telemetry or a learning artifact, decides an instruction
  should change, and edits it through the ordinary PR path.
- ADR-0002 shields personal learning signals from observation, which
  constrains question 5 (a learned rule cannot be derived from one person's
  private signals without their consent) but does not answer it.
- ADR-0005 stops agent delivery at human acceptance, which is the strongest
  existing answer to question 2 for the delivery path — but it governs code
  changes, not control-artifact changes proposed from telemetry.

## End state

**A. Close it.** An accepted ADR under `docs/architecture/adr/` that answers
all six questions with a mechanism, each paired with the path or contract
that implements it. Minimum content:

| Question | The ADR must name |
| --- | --- |
| Trigger signal | A concrete event or threshold in an existing telemetry or evidence schema — not "findings" |
| Automatic vs approved | The gate. The default that fits ADR-0005 is: the loop *proposes* (opens a PR or a `future/` artifact); a human accepts |
| Causality vs correlation | The comparison the proposal must carry — at minimum, the same task class before and after, with the confound the reviewer should check |
| Rollback | The revert path and the signal that triggers it; a learned instruction is a governed control artifact and reverts through the same PR path as any other |
| Overfitting to one developer | The population floor, or the explicit statement that this instance is single-developer and the floor is deferred, consistent with ADR-0002 |
| Knowing it helped | The outcome measure the proposal committed to *before* acceptance, and where the post-acceptance reading of it is recorded (`evidence/`) |

## Recommendation

Open A as an ADR *proposal* only after the telemetry side can produce a
per-instruction outcome measure — without that, questions 3 and 6 have no
honest answer and the ADR would be conceptual in exactly the way this file is
trying to end.

## How to verify

After A: each of the six questions has a one-line answer in the ADR that
points at a repo-relative path, and the manifest hook can cite the ADR when
an instruction changed because of it.

## Out of scope

- Building the automated proposer. This file scopes the decision, not the
  implementation.
- Changing ADR-0002 or ADR-0005. The answer here must fit inside them.
