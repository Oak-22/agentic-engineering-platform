# Architecture Decision Records

This directory is the repository-wide register for durable architecture
decisions. Keep ADRs centralized here, including decisions that affect only one
platform domain. Declare the affected subsystem in frontmatter rather than
creating per-component ADR directories.

## Frontmatter schema

Every ADR must begin with YAML frontmatter using this shape:

```yaml
---
title: Separate implementation knowledge from organizational governance
summary: Define canonical ownership across Git, Confluence, and Jira.
adr: ADR-0001
status: accepted
date: 2026-07-27
scope: repository
affected_components:
  - platform/agent-control-plane
related_jira: []
related_confluence: []
supersedes: []
---
```

Required fields:

| Field | Type | Allowed values or format |
| --- | --- | --- |
| `title` | string | Human-readable decision title |
| `summary` | string | One sentence explaining the decision's purpose or boundary |
| `adr` | string | `ADR-` followed by a unique four-digit sequence |
| `status` | string | `proposed`, `accepted`, `superseded`, or `deprecated` |
| `date` | string | Decision date in `YYYY-MM-DD` form |
| `scope` | string | `repository`, `platform`, `component`, or `integration` |
| `affected_components` | array | One or more repository-relative component paths, or `repository` for a repository-wide concern |

Optional relationship fields are arrays of stable identifiers or URLs:

- `related_jira`
- `related_confluence`
- `supersedes`

Put `title` and `summary` first. Human-oriented renderers should present them
as the page heading and short context before rendering the remaining metadata.
The Markdown H1 must match `title` so basic Markdown previews remain readable.

Use `scope` for the decision's architectural reach and
`affected_components` for the concrete systems it governs. A cross-cutting
decision may list several components; it does not need to be duplicated.

## Record format

Name records `NNNN-short-decision-title.md`. Keep the body concise:

1. **Context** — the forces and boundary that require a decision.
2. **Decision** — the chosen rule.
3. **Consequences** — important benefits, costs, and follow-up implications.
4. **Alternatives considered** — materially different options that were
   rejected.

Do not rewrite an accepted ADR to reverse its decision. Add a new ADR and list
the earlier record under `supersedes`.

## Decisions

- [ADR-0001: Separate implementation knowledge from organizational governance](0001-separate-implementation-knowledge-from-organizational-governance.md)
- [ADR-0002: Shield personal learning signals from observation](0002-shield-personal-learning-signals-from-observation.md)
- [ADR-0003: Adopt LangGraph and LangSmith as orchestration and telemetry backends](0003-adopt-langgraph-and-langsmith-as-orchestration-and-telemetry-backends.md)
- [ADR-0004: Move the GitHub MCP surface to a remote transport](0004-move-github-mcp-to-a-remote-transport.md)
