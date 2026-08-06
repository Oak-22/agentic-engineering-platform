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
- `mcp-servers/` contains provider-neutral MCP server definitions — tool and
  resource connectors an agent may use.

## Adapter rule

Runtime-native installation surfaces may import, link, or translate these
assets:

- `.agents/` provides Codex skill discovery links.
- `.codex/` provides Codex project configuration and lifecycle hooks.
- `.claude/` provides Claude Code discovery adapters.
- Agent-related `.github/` paths provide GitHub Copilot discovery adapters.

Adapters contain only discovery metadata and runtime-specific configuration.
Canonical shared instructions, skill packages, hook definitions, execution
policies, and role charters remain here. Runtime-specific discovery,
permissions, hooks, and enforcement configuration stay in their runtime-native
installation surface or are rendered by `../adapters/runtimes/`.
