---
title: Shield personal learning signals from observation
summary: Separate the personal learning store, the nomination queue, and aggregate recall telemetry into three stores with distinct visibility.
adr: ADR-0002
status: proposed
date: 2026-08-18
scope: component
affected_components:
  - platform/developer-learning-retrieval
  - platform/inference-telemetry-observatory
related_jira: []
related_confluence: []
supersedes: []
---

# Shield personal learning signals from observation

## Context

Developer Learning Retrieval turns engineering activity into spaced retrieval
practice, then promotes durable lessons outward through `personal → repo →
domain → global`. Two commitments in the current design contradict each other.

The personal learning store is described as private, machine-local, and
uncommitted. Promotion, however, requires that someone other than the author
evaluate a lesson's reusability. A store nothing can observe cannot supply
candidates to a review gate, so the promotion arrow cannot fire. The design
must either open the personal store or change how candidates reach review.

Opening it is the intuitive fix and the wrong one. The personal store's value
is that it holds *weak* signals: half-formed confusion, recorded misconceptions
and assumptions, and reflection written before the author understands the
problem. Those signals are honest only while unobserved. An opt-in that grants
a reviewer read access is consent-gated observation rather than privacy, and a
developer who knows the store is read will write for the reader. The mechanism
would degrade the input it exists to collect.

Retrieval results are a separate matter. Recall attempts produce confidence,
misconceptions, and outcomes, which are useful to a team lead in a way prose
notes are not — they are comparable across people and identify shared gaps.
They are also, unavoidably, performance data about individuals. Organizational
knowledge quizzes that are deliberately kept out of performance review suggest
these signals are valuable precisely when they carry no evaluative consequence.

The single-store-with-a-sync approach fails because it ships prose reflection
and performance data through one channel, blurring a boundary this design
exists to draw.

## Decision

Learning signals live in three stores, distinguished by visibility rather than
by access control on one store.

| Store | Visibility | Contents |
| --- | --- | --- |
| Personal learning store | Author only. Never synced; readable only by the author's own local tooling. | Weak signals: confusion, misconceptions, assumptions, reflection, raw recall attempts. |
| Nomination queue | Team, through the repository's normal review path. | Candidate lessons the author deliberately copied out of the personal store. |
| Aggregate recall telemetry | Team lead and team. | Concept-keyed, person-anonymous recall statistics. |

The following rules govern them.

**No disclosure path out of the personal store.** Its contents reach no other
person and no shared surface. Local processing on the author's own machine, for
the author's own session — generating their prompts, scheduling their reviews —
is not disclosure and is expected; the constraint is on what leaves, not on what
the author's own tooling may compute. Promotion candidates leave only when the
author copies them out. Nomination is an authoring act, not an export the system
performs on the author's behalf.

**Promotion is by submission, not inspection.** A nominated candidate enters
the queue as a normal reviewed change. A lead evaluates nominations, may
cross-reference nominations from peers, and may decline. No promotion is
guaranteed, and declining a nomination produces no record in the author's
personal store.

**Review authority is exercised through review, not write access.** No role
receives write access to another developer's learning space. Promotion outward
is a merge into shared scope, subject to the repository's existing governed
delivery path.

**Recall telemetry is person-anonymous and evaluation-excluded.** Statistics
are keyed by concept, never by person. A concept's statistics are emitted only
when the contributing cohort meets a minimum size, so that small teams cannot
re-identify an individual from a single data point; the platform suppresses the
statistic otherwise. Recall performance must not be used as an input to
performance evaluation, compensation, or promotion of the person, and the
contract states this where developers will read it.

**The personal store is not platform-retained.** It remains machine-local. The
platform defines its schema so nominations are well-formed, and stores none of
its content.

**These three stores belong to Developer Learning Retrieval.** The domain
defines and operates them itself, and the loop runs to completion with nothing
mounted beside it. The nomination queue is the single surface a downstream
consumer may read; anything optional that a developer chooses to add reads from
there, on its own terms, and no part of this design waits on it.

## Consequences

- Weak signals stay honest, because the store that holds them carries no
  audience.
- A lead gains a cross-team view of which concepts are weakly held without
  learning who holds them weakly, which is a more comparable signal than
  reading individual prose would produce.
- Lessons a developer never thinks to nominate are never discovered. This is
  the real cost of the inversion, and aggregate telemetry only partly offsets
  it by pointing at concepts rather than at lessons.
- Nomination friction becomes load-bearing. If nominating is laborious, nothing
  is nominated and the promotion ladder starves. Nomination must be a
  first-class, low-cost action in the retrieval session itself.
- Small teams will see most concept statistics suppressed by the cohort
  minimum. This is correct behavior, not a defect, and it means the aggregate
  view is not useful until a team reaches a workable size.
- The three stores need three schemas rather than one, and the boundary between
  them has to be enforced mechanically rather than by convention if it is to
  hold.

## Alternatives considered

### Sync the personal store and grant the lead read access

Rejected. It converts opt-in privacy into consent-gated observation, causes
authors to write for the reader, and destroys the weak signals that justify
having a personal store at all. It also ships reflection and performance data
through one channel.

### Give the lead write access to each developer's shared space

Rejected. It places promotion authority in a direct write path that bypasses
the repository's reviewed delivery model, and it fragments shared knowledge
into one space per developer, which works against the convergence that
promotion exists to produce.

### One store with per-directory access control

Rejected. Access control on a single store makes the boundary a configuration
value that can be widened later without an architectural decision. Separate
stores make widening it a visible structural change.

### Person-keyed recall results with a policy commitment not to use them

Rejected. A policy that data will not be used evaluatively is an interpretive
control over data that remains technically available. Anonymizing at collection
makes the guarantee structural, which is the stronger position on the
control-artifact assurance spectrum.
