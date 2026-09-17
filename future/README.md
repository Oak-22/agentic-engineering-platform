# Future

A provisional design-doc store: repository-coupled plans shaped enough to
keep but deliberately not yet activated as Jira work. It is unordered; a
ranked list of these is a backlog, and that lives in Jira. The lifecycle
below is proposed in [deferred-intent-lifecycle-adr.md](deferred-intent-lifecycle-adr.md) and
not yet an accepted ADR.

## What belongs here

A file enters `future/` when all of these hold:

- the intent is implementation-coupled and specific to this repository;
- losing its research, constraints, or proposed structure would cost real
  reconstruction effort;
- delivery is intentionally postponed;
- no canonical document already owns the same intent.

## What does not

| Instead of `future/` | Use |
| --- | --- |
| Spontaneous file changes that already exist | atomic commits on `workbench/local` |
| Work that is activated | a Jira work item; the `future/` file remains its scope brief until merge |
| Durable decisions or rationale | `docs/architecture/adr/`, `docs/strategy/` |
| Completed plans | nothing — delete the file; Git, Jira, and the pull request keep the history |

`future/` is the only store for provisional intent. Jira holds work from
activation onward.

## Leaving

The delivery pull request that realizes a plan must promote its durable
content into an ADR or canonical documentation, delete the file, or split
unrealized residue into a new bounded file. Everything still here describes a
state that has not reached `main`.

## Writing a plan

Start from [traceable-change-plan-template.md](traceable-change-plan-template.md)
when the change is too large to review in one pass. Open with status, state
the end condition rather than a task list, and cite exact paths.
