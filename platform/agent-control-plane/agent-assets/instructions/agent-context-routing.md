# Agent Context Routing

## Purpose

Define an artifact-typed control plane for repository-aware AI agents while
preserving safe migration semantics.

## Layer model

1. Lightweight repository entrypoints load shared, always-applicable rules.
2. Lightweight runtime adapters satisfy native discovery contracts.
3. Shared agent assets hold reusable instructions, skills, role charters, and
   workflow definitions.
4. Runtime-native hooks, permissions, CI, rulesets, and IAM enforce mechanical
   boundaries.

## Discovery boundary

Runtime-discovered entrypoints and adapters belong at the repository root.
Canonical reusable content belongs under
`platform/agent-control-plane/agent-assets/`.

## Local overlay rule

Optional local overlays may hold personal workflow behavior. They cannot
define canonical product requirements or runtime contracts.
