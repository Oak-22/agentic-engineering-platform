# Agent Instructions

Load repository instructions from `.github/agent_instructions/` before
making code, documentation, data-layout, or Git changes in this repo.
Before making changes, report the instruction files read for this task.

## Discovery Paths

Generic repo-first agents should start here:

```text
AGENTS.md
  -> .github/agent_instructions/agent.md
  -> .github/agent_instructions/README.md
  -> .github/agent_instructions/global/README.md
  -> .github/agent_instructions/repo/README.md
  -> task-relevant instruction files
```

Runtime-specific adapters, such as GitHub Copilot instructions, should
also converge on the same instruction tree.

## Canonical Load Order

1. `.github/agent_instructions/agent.md`
2. `.github/agent_instructions/README.md`
3. `.github/agent_instructions/global/README.md`
4. `.github/agent_instructions/repo/README.md`
5. Task-relevant files referenced by those indexes

## Layer Model

- `global/`: reusable guidance shared across repositories
- `repo/`: repository-specific context, boundaries, and constraints

Global guidance supplies default decision rules. Repo guidance supplies
local facts and constraints that shape or override those defaults.
