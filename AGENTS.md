# Repository Agent Guidance

## Repository purpose

This repository is the canonical Agentic Engineering Platform monorepo. It
owns reusable agent governance, inference telemetry, developer learning,
shared contracts and tooling, and evidence from applied workflows. Downstream
product repositories remain independently governed consumers.

## Working rules

- Read the root `README.md` and the nearest component documentation before
  changing architecture or ownership boundaries.
- Preserve user-authored and unrelated work.
- Keep changes scoped and use existing repository patterns before introducing
  new abstractions.
- Treat generated artifacts as derived output and verify them against their
  canonical source.
- Never commit credentials, private knowledge overlays, or machine-specific
  paths.
- Run the smallest relevant checks and report anything that could not be
  verified.

## Agent customization layout

- `AGENTS.md` is the shared, automatically discovered repository guidance for
  Codex and other agents that support the AGENTS.md convention.
- `CLAUDE.md` is the Claude Code repository adapter and imports `AGENTS.md`.
- `.github/copilot-instructions.md` is the GitHub Copilot repository adapter.
- `.agents/`, `.codex/`, `.claude/`, and the agent-related `.github/` paths are
  thin runtime-native installation surfaces for Codex, Claude Code, and
  GitHub Copilot. They do not own canonical reusable behavior.
- `.github/agents/`, `.github/prompts/`, `.github/skills/`, and
  `.github/hooks/` contain provider-required GitHub Copilot definitions and
  discovery adapters.
- `platform/agent-control-plane/agent-assets/` owns canonical shared
  instructions, skills, hook definitions, execution policies, and role
  charters.
- `platform/agent-control-plane/` owns the portable contracts, canonical agent
  assets, runtime and destination adapters, validation, and explanatory
  documentation behind those root entrypoints.

When changing the agent customization system, read
`platform/agent-control-plane/README.md` and
`platform/agent-control-plane/agent-assets/instructions/agent-context-routing.md`.
