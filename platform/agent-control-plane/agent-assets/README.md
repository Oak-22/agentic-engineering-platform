# Shared Agent Assets

This directory owns reusable model-neutral instructions and role charters.
Canonical skill packages live under the repository-root `.agents/skills/`
surface; Claude Code and GitHub Copilot link to those packages.

## Asset boundaries

- `instructions/` contains shared behavioral and path-oriented guidance.
- `role-charters/` contains runtime-neutral responsibilities, boundaries, and
  accountability definitions for specialized agents.

## Adapter rule

Runtime-owned paths may import, link, or translate these assets:

- `.agents/` owns canonical provider-neutral skill packages, including
  colocated workflow references.
- `.claude/` provides Claude Code discovery adapters.
- `.github/` provides GitHub Copilot discovery adapters.

Adapters contain only discovery metadata and runtime-specific configuration.
Canonical shared instructions and role charters remain here. Canonical skill
procedures and references remain under `.agents/skills/`. Runtime-specific
permissions, hooks, and enforcement configuration stay in their native
adapter namespace.
