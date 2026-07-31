# Agent Context Routing

## Purpose

Define an artifact-typed control plane for repository-aware AI agents while
preserving safe migration semantics.

## Layer model

1. Lightweight repository entrypoints load shared, always-applicable rules.
2. Canonical provider-neutral skill packages live under `.agents/skills/`.
3. Lightweight Claude Code and GitHub Copilot adapters satisfy native
   discovery contracts.
4. Shared agent assets hold reusable instructions and role charters.
5. Runtime-native hooks, permissions, CI, rulesets, and IAM enforce mechanical
   boundaries.

## Discovery boundary

Runtime-discovered entrypoints, canonical skill packages, and adapters belong
at the repository root. Canonical reusable instructions and role charters
belong under `platform/agent-control-plane/agent-assets/`.

## Local overlay rule

Optional local overlays may hold personal workflow behavior. They cannot
define canonical product requirements or runtime contracts.
