---
description: "Use when changing instruction layering, agent roles, prompt artifacts, skills, hooks, or migration boundaries."
applyTo: "AGENTS.md,.github/**/*.md,.github/**/*.json,platform/agent-control-plane/**,docs/**/*.md"
---
# Agent Context Routing

## Purpose

Define a modern, artifact-typed control plane for repository-aware AI
agents while preserving safe migration semantics.

## Active checked-in paths

- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.github/instructions/*.instructions.md`
- `.github/agents/*.agent.md`
- `.github/prompts/*.prompt.md`
- `.github/skills/*/SKILL.md`
- `.github/hooks/*.json`

## Discovery boundary

Runtime-discovered repository entrypoints belong at the Git root. A nested
`.github/` directory is template data unless that nested directory is opened as
the workspace root.

Use root `AGENTS.md` for shared agent guidance, root
`.github/copilot-instructions.md` for Copilot-specific routing, and root
`.github/instructions/*.instructions.md` for path-scoped Copilot behavior.
Keep portable contracts and adapter implementations under
`platform/agent-control-plane/`.

## Local Overlay Rule

Optional local overlays may exist for personal workflow behavior, but
must not define canonical product requirements or runtime contracts.
