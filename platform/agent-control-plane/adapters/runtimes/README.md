# Provider Runtime Adapters

This directory owns capability and version mappings for agent runtimes such as
Codex, Claude Code, and GitHub Copilot. Provider scaffolds may document an
intended adapter boundary before the first declaration or renderer exists;
executable or declarative artifacts should be added only for concrete runtime
needs.

Each adapter must identify the canonical schema versions and provider versions
it supports, render provider-native discovery or policy artifacts, and report
unsupported semantics without weakening canonical intent. Repository-root
runtime paths remain generated or linked discovery outputs rather than
canonical sources.

## Providers

- [`codex/`](codex/) maps canonical assets into Codex project configuration,
  hooks, Agent Skills, and role definitions.
- [`claude/`](claude/) maps canonical assets into Claude Code settings, rules,
  hooks, skills, and subagent definitions.
- [`github-copilot/`](github-copilot/) maps canonical assets into GitHub
  Copilot instructions, prompts, skills, agents, and hooks.
