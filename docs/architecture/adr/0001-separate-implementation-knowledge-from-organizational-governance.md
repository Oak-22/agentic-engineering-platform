---
title: Separate implementation knowledge from organizational governance
summary: Define canonical ownership across Git, Confluence, and Jira.
adr: ADR-0001
status: accepted
date: 2026-07-27
scope: repository
affected_components:
  - repository
related_jira: []
related_confluence: []
supersedes: []
---

# Separate implementation knowledge from organizational governance

## Context

The Agentic Engineering Platform uses Git, Jira, and Confluence. Without a
clear ownership boundary, technical documentation can be copied into
Confluence, governance can become buried in repository files, and delivery
state can be repeated in both.

The five systems under `platform/` are durable architectural domains within
one platform monorepo. They are not, by that fact alone, independent products,
Jira projects, permanent epics, or separate documentation systems. A domain
describes stable architectural ownership; an epic describes a time-bounded
delivery outcome.

## Decision

Each system owns a different kind of information:

- **Git** owns implementation-coupled knowledge and enforcement: architecture
  decision records, developer and agent documentation, schemas, contracts,
  runtime instructions, adapters, technical runbooks, and architecture that
  describes implemented behavior.
- **Confluence** owns organizational governance and knowledge that evolves
  independently of repository changes: enterprise policy, organizational
  roles, authorization policy, risk and exception processes, cross-system
  proposals, and decision or governance meeting records.
- **Jira** owns accountable execution: work scope, responsible human, delivery
  status, approval mode, and links to the relevant Git and Confluence sources.

Content has one canonical owner. Other systems link to it and may provide a
short orientation, but do not maintain a second full copy.

ADRs are stored centrally in `docs/architecture/adr/`. Their `scope` and
`affected_components` metadata identify the relevant subsystem or integration.

The directories under `platform/` remain architectural domains. Jira may
represent these domains using stable classification metadata, while epics and
projects remain reserved for delivery initiatives and independently governed
products respectively.

## Consequences

- Agent and developer documentation stays reviewable and versioned with the
  implementation it controls.
- Enterprise policy can evolve through organizational review without creating
  repository-only governance.
- Jira work remains traceable without becoming a documentation store.
- Cross-system pages and work items must link to their canonical source.
- A policy may be stated in Confluence while its technical enforcement lives
  in Git; both should link to each other.
- Platform-domain classification in Jira is useful, but its field design and
  rollout require a separate delivery decision or task.

## Alternatives considered

### Mirror technical documentation into Confluence

Rejected because two editable copies create unclear ownership and predictable
drift.

### Store all documentation in Git

Rejected because organizational policy, roles, and governance discussions have
different contributors, review paths, and change triggers.

### Create ADR collections inside each platform subsystem

Rejected for now because it fragments discovery and obscures cross-cutting
decisions. Central metadata provides the needed subsystem relationship with
less structure.

### Represent each platform domain as a Jira project or permanent epic

Rejected because source-tree modules are not automatically autonomous products,
and permanent epics become unbounded delivery buckets.
