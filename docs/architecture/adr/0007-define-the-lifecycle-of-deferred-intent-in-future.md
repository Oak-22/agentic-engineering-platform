---
title: Define the lifecycle of deferred intent in future/
summary: Make future/ the repository's only provisional design-doc store, with entry criteria, a Captured / Activated / Realized / Withdrawn lifecycle, activation into Jira, terminal disposition on the delivering pull request, and retirement of the Jira Scratchboard status.
adr: ADR-0007
status: accepted
date: 2026-09-17
scope: repository
affected_components:
  - repository
related_jira:
  - AEPI-156
related_confluence: []
supersedes: []
---

# Define the lifecycle of deferred intent in future/

## Context

The repository has two pre-delivery patterns:

```text
implementation-first
IDE change -> workbench/local -> shape -> Jira delivery

intent-first
research and detailed plan -> future/ -> activate in Jira -> delivery
```

`workbench/local` fits spontaneous implementation whose delivery boundary
emerges after files have already changed. It is a poor fit for a
well-developed feature, fix, or architectural idea that should be postponed
without losing its repository-specific research, constraints, and reasoning.

Sending that detail straight to Jira creates a semantic round trip: intent
leaves the IDE, becomes external task text, and later has to be fetched and
reconstructed in repository context. Jira still owns execution state and
authority, but implementation-coupled meaning should not depend on that
round trip. Kubernetes enhancement proposals, Rust RFCs, and Go design docs
hold the same state under their own names.

Before this record, the repository described `future/` as holding shaped but
not implemented change plans and defined nothing else: no entry criteria,
activation, authority transfer, terminal disposition, cancellation, or
residual-work rule. Without those rules the directory can drift into a second
backlog (ranked, owned, duplicating Jira) or a completed-plan archive. At the
same time the Jira project carried a `Scratchboard` status that competed with
`future/` for the same content.

## Decision

`future/` is the repository's only provisional design-doc store: the
repository-native home for nuanced, implementation-coupled intent that is
developed enough to preserve but not yet activated as Jira work. It is
unordered and unowned; prioritization belongs to Jira.

### Lifecycle

| State | Meaning | Authority |
| --- | --- | --- |
| Captured | Nuanced intent is preserved and deliberately inactive | The `future/` artifact owns implementation-coupled detail; no Jira record is required |
| Activated | Accountable work and delivery have started, but the intended state is not yet on `main` | Jira owns priority, status, owner, and authorization; the artifact remains the implementation scope brief |
| Realized | The intended state has reached `main` | Code, tests, ADRs, and canonical documentation own durable truth; Jira and the pull request own delivery history |
| Withdrawn | The intent is no longer intended for delivery | Git history preserves the removed proposal and its withdrawal rationale |

### Entry

Place an artifact in `future/` when all of the following hold:

- the intent is implementation-coupled and repository-specific;
- enough research, constraints, or proposed structure exists that losing it
  would create meaningful reconstruction cost;
- implementation or delivery is intentionally postponed; and
- no existing canonical document already owns the same intent.

Do not use `future/` for spontaneous file changes that already exist; capture
and shape those through `workbench/local`. Do not use it as a substitute for
Jira once work is activated, or as an archive for completed plans.

A captured artifact carries no required metadata. Prose plus, once activated,
a reference to its Jira key is sufficient: the artifact's state is legible
from its text and from `main` (captured while it exists there and no Jira item
references it; activated while a Jira item does; realized once it is gone).
A metadata schema would turn planning into form-filling and would duplicate
state that Jira and Git already hold.

### Activation

When the intent becomes active work:

1. Shape the accountable outcome and create or resolve the Jira work item.
2. Keep Jira concise: record execution state, ownership, acceptance, and a
   reference to the repository plan instead of duplicating its detail.
3. Create the delivery branch from current `main` under the governed delivery
   workflow.
4. Carry the `future/` artifact as the implementation scope brief while the
   intended state remains absent from `main`.
5. Treat material edits to its outcome or boundaries as explicit scope
   changes.

Activation does not make the artifact historical. Relative to `main`, its
described state is still future until the delivery merges.

### Terminal disposition

The delivering pull request must leave each activated artifact in one of
three terminal conditions:

1. **Promote** durable decisions or explanations into an ADR or canonical
   documentation and remove the consumed artifact.
2. **Delete** the artifact when code, tests, and delivery records fully embody
   its intent and no durable explanatory content remains.
3. **Split** unrealized residual intent into newly bounded `future/`
   artifacts, then remove the consumed parent.

There is no `future/completed/`. Git history, Jira, and pull requests already
preserve execution evidence. Everything under `future/` describes an intended
state that has not yet reached `main`.

An umbrella artifact whose residue activates across several outcomes at
different times is split on first activation: the pull request that realizes
the first outcome removes the umbrella and leaves one bounded artifact per
unrealized remainder. Each remainder then follows the lifecycle on its own,
so no artifact is ever partly realized on `main` and partly future.

### Cancellation and reactivation

- Permanently withdrawn intent leaves `future/`; the removing commit or the
  associated Jira record preserves a concise rationale.
- Temporarily deactivated Jira work may remain in `future/` only when its
  intended state is still valid and the artifact returns to captured status
  without claiming active authorization.
- Reactivation revalidates the artifact against current `main`; stale paths,
  assumptions, and dependencies are evidence to reshape it, not instructions
  to reproduce obsolete implementation.

### Jira Scratchboard

A Jira work item exists from activation onward; nothing in Jira represents
deliberately inactive intent. The Jira project's `Scratchboard` status is
retired. It has no description; it shares the `To Do` status category, so
board counts and category queries cannot tell uncommitted intent from
activated work; and it competes with `future/` for the same content, so
shaped, repository-coupled intent lands in whichever surface the author is in
at the moment, with no cross-links between the two stores. Scoping it to
non-repository deferred intent does not justify a second store: that class of
work has not appeared, and when it does it enters Jira as activated work like
any other.

Raw ideas too thin for a `future/` artifact stay on `workbench/local` as
atomic commits or become a short `future/` note; they do not become a Jira
issue until activated.

## Consequences

- `README.md` and `docs/operations/governed-repository-delivery.md` describe
  `future/` in these terms, and the delivery guide carries the intent-first
  entry path and the terminal-disposition rule beside the workbench path.
- `shape-repository-change` reports the `future/` plan a candidate realizes so
  the Jira item activates it as scope brief and the delivering pull request
  owes it a terminal disposition. Teaching `deliver-governed-change` to
  activate a plan without copying its semantics into Jira, and to require the
  terminal disposition before it reports the unit complete, is follow-up work.
- Retiring the `Scratchboard` status and relocating the shaped body of the
  one item in that column are Jira configuration work delivered separately.
- Existing `future/` artifacts are read against these criteria as they are
  touched; they are not rewritten to make the directory uniform.
- The workbench rest state defined in the delivery guide (equality with
  `main` after post-merge cleanup) means a `future/` artifact reaches `main`
  through its own pull request rather than living on `workbench/local`. Two
  questions remain deliberately open and belong to the rest-state gate that
  follows this record: whether activation requires the artifact to be on
  `main` first, and the smallest deterministic check that keeps a realized
  artifact from lingering under `future/`. Both are gating questions about
  `main` versus `workbench/local`, so they are decided where that gate is
  defined.
- This record is the bootstrap case: its own draft was captured under
  `future/`, activated through AEPI-156, and promoted here, ending the
  recursion.

## Alternatives considered

- **Jira as the only pre-delivery store.** Rejected: it forces the semantic
  round trip described above and strips repository context from
  implementation-coupled intent.
- **Required metadata on every artifact** (state, owner, Jira key as
  frontmatter). Rejected: it duplicates state Jira and Git already hold and
  makes capture heavier than the intent it preserves.
- **Keep `Scratchboard` scoped to non-repository deferred intent.** Rejected:
  no such work has appeared, and a second provisional store with no
  cross-links reintroduces the ambiguity this record removes.
- **A `future/completed/` archive.** Rejected: Git history, Jira, and pull
  requests already preserve the record, and an archive invites the directory
  to stop meaning "not yet on `main`".
- **Retire an umbrella artifact only when its last remainder lands.**
  Rejected: it leaves one file partly realized and partly future, which is
  exactly the state the directory's invariant forbids.
