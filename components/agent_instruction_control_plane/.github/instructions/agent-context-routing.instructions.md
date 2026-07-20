---
description: "Use when changing instruction layering, agent roles, prompt artifacts, skills, hooks, or migration boundaries."
applyTo: ".github/**/*.md, .github/**/*.json, docs/**/*.md"
---
# Agent Context Routing

## Purpose

Define a modern, artifact-typed control plane for repository-aware AI
agents while preserving safe migration semantics.

## Active Checked-In Paths

- `.github/copilot-instructions.md`
- `.github/instructions/*.instructions.md`
- `.github/agents/*.agent.md`
- `.github/prompts/*.prompt.md`
- `.github/skills/*/SKILL.md`
- `.github/hooks/*.json`

## Migration Rule

Legacy paths such as `AGENTS.md` and `.github/agent_instructions/`
should be treated as deprecated migration references, not active
canonical surfaces.

When modernizing a repository, migrate behavior into
`.github/instructions/*.instructions.md` and remove legacy path
references once routing is fully updated.

## Local Overlay Rule

Optional local overlays may exist for personal workflow behavior, but
must not define canonical product requirements or runtime contracts.
