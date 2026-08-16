# Claude Skill Catalog

This directory exposes the canonical packages under
`platform/agent-control-plane/agent-assets/skills/` to Claude Code through
relative symlinks.

## Repository skills

- `deliver-governed-change` — Coordinate a traceable change across work tracking, documentation, code, review, and closure.
- `handoff-agent-work` — Preserve intent, evidence, authority, and state when work moves between agents or runtimes.
- `manage-git-workflow` — Govern branches, commits, pushes, pull requests, merges, and cleanup.
- `manage-jira-confluence` — Read and update Jira and Confluence as one traceable Atlassian workflow.
- `shape-repository-change` — Turn repository observations and changes into coherent delivery-unit candidates.
- `shape-readme-entrypoint` — Keep a repository README focused on orientation and a hands-on quick start.
- `show-me` — Capture a diagram and explanation of a resolved or in-progress mechanism into a personal, machine-local knowledge base.

## Anthropic reference skills

Anthropic publishes example and reference skills on its own release schedule,
independent of this repository. Rather than maintain a dated snapshot of that
catalog here — which drifts every time Anthropic adds or updates an entry —
consult it directly:

- [Anthropic skills repository](https://github.com/anthropics/skills)

Anthropic describes these as examples and reference implementations; behavior
can differ across Claude products. A skill appearing in that catalog is not
installed in this repository merely by existing there.

## Using the catalog

Study the closest official skill before authoring a custom one, then keep the
custom workflow focused on a distinct trigger, input, output, and success
condition. Install a reference skill only when the repository should depend on
its behavior; otherwise use it as a design reference.
