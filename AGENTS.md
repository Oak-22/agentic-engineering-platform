# Repository Agent Guidance

## Repository purpose

This repository is the canonical Agentic Engineering Platform monorepo. It
owns reusable agent governance, telemetry, context tooling, shared contracts,
and evidence from applied workflows. Product repositories such as `myHealth`
remain downstream consumers and proving grounds.

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
- `.github/copilot-instructions.md` is the GitHub Copilot repository adapter.
- `.github/CLAUDE.md` is the Claude repository adapter.
- `.github/instructions/` contains path-specific Copilot instructions.
- `.github/agents/`, `.github/prompts/`, `.github/skills/`, and
  `.github/hooks/` contain runtime-specific agent assets.
- `.agents/skills/` contains Codex skill-discovery adapters that point to the
  canonical skills under `.github/skills/`.
- `platform/agent-control-plane/` owns the portable contracts, adapters,
  validation, and explanatory documentation behind those root entrypoints.

When changing the agent customization system, read
`platform/agent-control-plane/README.md` and
`.github/instructions/agent-context-routing.instructions.md`.
