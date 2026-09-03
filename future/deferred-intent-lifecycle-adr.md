# TODO: Define the lifecycle of deferred intent in `future/`

Status: proposed capture only. This artifact is intentionally exercising the
lifecycle it proposes; it is not yet an accepted ADR or active Jira delivery.

Primary classification: architecture/docs

## Summary

Define `future/` as the repository-native home for nuanced,
implementation-coupled intent that is sufficiently developed to preserve but
not yet activated as Jira work. Specify how an artifact enters `future/`, how
it participates in delivery after activation, and how it leaves the directory
when the intended state reaches `main`.

## Problem

The repository has two different pre-delivery patterns:

```text
implementation-first
IDE change -> workbench/local -> shape -> Jira delivery

intent-first
research and detailed plan -> future/ -> activate in Jira -> delivery
```

`workbench/local` is effective for spontaneous implementation whose delivery
boundary emerges after files have already changed. It is a poor fit for a
well-developed feature, fix, or architectural idea that should be postponed
without losing its repository-specific research, constraints, and reasoning.

Sending all of that detail directly to Jira creates a semantic round trip:
intent leaves the IDE, becomes external task text, and later has to be fetched
and reconstructed in repository context. Jira still needs to send execution
state and authority back to the agent, but implementation-coupled meaning
should not depend on that round trip.

The current repository description says that `future/` holds shaped but not
implemented change plans, but it does not define entry criteria, activation,
authority transfer, terminal disposition, cancellation, or residual work.
Without those rules, the directory can become a second backlog or a completed
plan archive.

## Proposed lifecycle

| State | Meaning | Authority |
| --- | --- | --- |
| Captured | Nuanced intent is preserved and deliberately inactive | The `future/` artifact owns implementation-coupled detail; no Jira record is required |
| Activated | Accountable work and delivery have started, but the intended state is not yet on `main` | Jira owns priority, status, owner, and authorization; the artifact remains the implementation scope brief |
| Realized | The intended state has reached `main` | Code, tests, ADRs, and canonical documentation own durable truth; Jira and the pull request own delivery history |
| Withdrawn | The intent is no longer intended for delivery | Git history preserves the removed proposal and its withdrawal rationale |

### Entry

Place an artifact in `future/` when all of the following are true:

- the intent is implementation-coupled and repository-specific;
- enough research, constraints, or proposed structure exists that losing it
  would create meaningful reconstruction cost;
- implementation or delivery is intentionally postponed; and
- no existing canonical document already owns the same intent.

Do not use `future/` for spontaneous file changes that already exist; capture
and shape those through `workbench/local`. Do not use it as a substitute for
Jira when work is already activated, or as an archive for completed plans.

### Activation

When the intent becomes active work:

1. Shape the accountable outcome and create or resolve the Jira work item.
2. Keep Jira concise: record execution state, ownership, acceptance, and a
   reference to the repository plan instead of duplicating its full detail.
3. Create the delivery branch from current `main` under the governed delivery
   workflow.
4. Carry the future artifact as the implementation scope brief while the
   intended state remains absent from `main`. Record its Jira key and activation
   state when that improves traceability.
5. Treat material edits to its outcome or boundaries as explicit scope changes.

Activation does not immediately make the artifact historical. Relative to
`main`, its described state is still future until the delivery merges.

### Terminal disposition

The delivery pull request must leave each activated artifact in one of three
terminal conditions:

1. **Promote** durable decisions or explanations into an ADR or canonical
   documentation and remove the consumed future artifact.
2. **Delete** the artifact when code, tests, and delivery records fully embody
   its intent and no durable explanatory content remains.
3. **Split** unrealized residual intent into newly bounded future artifacts,
   then remove the consumed parent.

Do not create `future/completed/`. Git history, Jira, and pull requests already
preserve historical execution evidence. Everything remaining under `future/`
must describe an intended state that has not yet reached `main`.

### Cancellation and reactivation

- Permanently withdrawn intent leaves `future/`; preserve a concise rationale
  in the removing commit or associated Jira record.
- Temporarily deactivated Jira work may remain in `future/` only when its
  intended state is still valid and the artifact is returned to captured
  status without claiming active authorization.
- Reactivation revalidates the artifact against current `main`; stale paths,
  assumptions, and dependencies are evidence to reshape it, not instructions
  to reproduce obsolete implementation.

## Proposed durable changes

- Record the accepted lifecycle as the next available repository ADR under
  `docs/architecture/adr/` and add it to the ADR register.
- Tighten the `future/` definition in `README.md` so it describes deferred
  intent rather than only unimplemented plans.
- Add the intent-first activation path and terminal-disposition rule to
  `docs/operations/governed-repository-delivery.md`.
- Teach `shape-repository-change` to route implementation-first evidence to
  the workbench path and shaped deferred intent to `future/`.
- Teach `deliver-governed-change` to activate a future artifact without
  copying its full semantics into Jira, then require its terminal disposition
  before merge completion.
- Audit the existing `future/` artifacts against the accepted entry and exit
  criteria without deleting or rewriting them merely to make the directory
  look uniform.

## Relationship to the cardinality and latency proposal

This proposal governs how deferred intent becomes active and where its meaning
lives. `future/governed-delivery-cardinality-latency-adr.md` separately governs
how active outcomes map to Jira tasks, branches, pull requests, commits, and
connector calls. The decisions can be reviewed independently. Their workflow
documentation and skill edits may be implemented together when doing so avoids
duplicated changes without collapsing the two decision records.

## Open decisions

- Decide whether future artifacts need lightweight required metadata for
  captured and activated states, or whether prose plus a Jira reference is
  sufficient.
- Decide whether a future artifact must reach `main` before Jira activation or
  may remain private on `workbench/local` until its delivery branch is created.
- Define how a shared umbrella artifact is retired when its residual work
  activates across multiple Jira outcomes at different times.
- Define the smallest deterministic check that prevents a realized artifact
  from remaining indefinitely under `future/` without turning planning into a
  schema-heavy workflow.

## Self-application and termination

This file is the bootstrap case for the proposed lifecycle. It begins in the
captured state. On activation, Jira should link to it and the delivery branch
should use it as the scope brief. The completing pull request should promote
the accepted rule into an ADR and canonical workflow guidance, remove this
file, and split only genuinely unrealized residual work into new future
artifacts. That terminal step ends the recursion.

## Explicit exclusions

- Do not create or update Jira, Confluence, an ADR, branches, pull requests, or
  commits as part of this capture.
- Do not modify the canonical workflow skills until the architectural decision
  is accepted.
- Do not modify or delete `prompt-scratch.md`.

