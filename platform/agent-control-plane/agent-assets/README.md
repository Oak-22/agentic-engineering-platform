# Shared Agent Assets

This directory owns reusable shared instructions, canonical Agent Skill
packages, and model-neutral role charters. Repository-root runtime discovery
paths link to these assets.

## Asset boundaries

- `instructions/` contains shared behavioral and path-oriented guidance.
- `skills/` contains canonical skill procedures, metadata, scripts,
  references, and other package resources.
- `hooks/` contains provider-neutral lifecycle definitions and intrinsic
  portable hook resources.
- `execution-policies/` contains provider-neutral bounded-execution policy
  instances.
- `role-charters/` contains runtime-neutral responsibilities, boundaries, and
  accountability definitions for specialized agents.

## Adapter rule

Runtime-owned paths may import, link, or translate these assets:

- `.agents/` provides Codex discovery adapters.
- `.claude/` provides Claude Code discovery adapters.
- `.github/` provides GitHub Copilot discovery adapters.

Adapters contain only discovery metadata and runtime-specific configuration.
Canonical shared instructions, skill packages, hook definitions, execution
policies, and role charters remain here. Runtime-specific discovery,
permissions, hooks, and enforcement configuration stay in their native
adapter namespace or are rendered by `../adapters/runtimes/`.
