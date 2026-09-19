# Close the feedback loop operationally

Status: to-do, not scheduled. Resolves by either an accepted ADR or a README
rewording (see *End state*). Delete this file when one of those lands.

## Context

`README.md` describes the platform as a feedback loop: the Agent Control
Plane governs execution, Inference Telemetry observes it, Developer Learning
converts validated signals into reusable improvements, and "telemetry findings
and validated learning feed back into the Agent Control Plane." The platform
diagram draws the forward arcs solid and the return arcs dotted.

The dotted arcs are honest — the return path is not built — but the prose
does not say so. A reader who takes the prose at face value asks six
questions the repository does not answer in any tracked artifact:

1. What exact signal triggers a proposed control change?
2. Is that change applied automatically or human-approved?
3. How is causality distinguished from correlation? (Did the instruction
   improve the outcome, or did the task mix change?)
4. How is a harmful learned rule rolled back?
5. How is overfitting to one developer prevented?
6. How does the system know a newly reinforced instruction improved outcomes?

The perception this creates: the loop is conceptually stronger than
operationally closed. That reading is correct today. What is missing is the
repository saying so, and saying what closing it would take.

## What exists today

Verified at the time of writing by reading the component READMEs and
`docs/architecture/`:

- The forward path is real. Instruction-load events are emitted per prompt
  (`.local-mirrors/instruction-evidence/`), the manifest hook cites them, and
  telemetry consumes the control plane's shared port rather than a copy.
- The return path is human-mediated and unstated. A developer reads
  telemetry or a learning artifact, decides an instruction should change,
  and edits it through the ordinary PR path. No artifact names that as the
  mechanism, and no artifact says it is deliberate.
- ADR-0002 shields personal learning signals from observation, which
  constrains question 5 (a learned rule cannot be derived from one person's
  private signals without their consent) but does not answer it.
- ADR-0005 stops agent delivery at human acceptance, which is the strongest
  existing answer to question 2 for the delivery path — but it governs code
  changes, not control-artifact changes proposed from telemetry.

## End state

One of two outcomes, chosen deliberately:

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

**B. Stop claiming it.** Reword `README.md` "Platform Model" and the diagram
caption so the return arcs are described as the current human-mediated path:
telemetry and learning artifacts are inputs a maintainer reads before
proposing an instruction change through the normal PR lifecycle. State that
an automated return path is not built and link this file until it is.

B is cheaper and can precede A. Doing B first removes the overclaim
immediately; A can then be scoped as a real delivery without the README
having promised it.

## Recommendation

Do B now, as a docs-only change. Open A as an ADR *proposal* only after the
telemetry side can produce a per-instruction outcome measure — without that,
questions 3 and 6 have no honest answer and the ADR would be conceptual in
exactly the way this file is trying to end.

## How to verify

After B: a reader of `README.md` alone can state who closes the loop today
(a maintainer, by PR) and cannot infer that any control artifact changes
without a human accepting it.

After A: each of the six questions has a one-line answer in the ADR that
points at a repo-relative path, and the manifest hook can cite the ADR when
an instruction changed because of it.

## Out of scope

- Building the automated proposer. This file scopes the decision, not the
  implementation.
- Changing ADR-0002 or ADR-0005. The answer here must fit inside them.
