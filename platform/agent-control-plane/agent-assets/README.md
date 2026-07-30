# Shared Agent Assets

This directory owns reusable, model-neutral agent content. Runtime discovery
surfaces at repository root remain thin adapters.

## Asset boundaries

- `instructions/` contains shared behavioral and path-oriented guidance.
- `skills/` contains reusable Agent Skills and their supporting files.
- `role-charters/` contains runtime-neutral responsibilities, boundaries, and
  accountability definitions for specialized agents.
- `workflow-definitions/` contains reusable task flows and prompt-independent
  execution sequences.

## Adapter rule

Runtime-owned paths may import, link, or translate these assets:

- `.agents/` provides Codex discovery adapters.
- `.claude/` provides Claude Code discovery adapters.
- `.github/` provides GitHub Copilot discovery adapters.

Adapters contain only discovery metadata and runtime-specific configuration.
Canonical policy and procedures remain here. Runtime-specific permissions,
hooks, and enforcement configuration stay in their native adapter namespace.
