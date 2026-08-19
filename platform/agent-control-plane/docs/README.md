# Documentation Map

This folder holds explanatory material for the agent control plane. It is not
the minimum install surface. Runtime-discovered entrypoints live at the
repository root in `AGENTS.md`, `CLAUDE.md`, `.agents/`, `.codex/`, `.claude/`,
and the agent-related `.github/` paths. Canonical reusable content lives in
`../agent-assets/`; an
`engineering-knowledge-base/` may be mounted separately as a private,
machine-local overlay.

## Start Here

- [Workbench-to-Delivery Branching](workbench-delivery-branching.md)
  Defines the clean integration base, private continuous
  capture-and-stewardship stream, dependency-ordered transfer, independent
  delivery branches, and local commit guardrail. Start with the
  [human operating guide](../../../docs/operations/governed-repository-delivery.md)
  when the detailed Git contract is not yet needed.
- [Agent Control Plane](diagrams/agent-control-plane.png)
  Visualizes how feedforward instructions, feedback checks, human
  review, and promotion loops interact.
- [Developer Learning Retrieval Service](../../developer-learning-retrieval/docs/design.md)
  Describes a future extension for turning engineering activity into
  learning and retrieval signals.
- [Local Documentation and Artifact Mirrors](local-doc-mirrors.md)
  Distinguishes the automatic provider-docs mirror, the automatic artifact
  archive, and manual artifact promotion into the repository.

## Diagrams

- [Agent Asset Discovery Layers](agent-asset-discovery-layers.md)
  Separates lightweight shared entrypoints and runtime adapters from the
  content-heavy canonical agent assets.
- [agent-control-plane.excalidraw](diagrams/agent-control-plane.excalidraw)
  Source file for the lifecycle diagram.
- [agent-control-plane.png](diagrams/agent-control-plane.png)
  Exported image for docs, portfolio use, and review.
- [LLM Diagram Manipulation Fidelity Experiment](../../../evidence/experiments/llm-diagram-manipulation-fidelity/README.md)
  Scaffold for comparing Mermaid-first and Excalidraw-native diagram
  update workflows.

## Strategy

- [Strategy Notes](strategy/README.md)
  Index for domain-agnostic strategy notes.

## Placement Rules

- Keep runtime-discovered entrypoints and runtime-native installation surfaces
  at root `AGENTS.md`, `.agents/`, `.codex/`, `.claude/`, and the agent-related
  `.github/` paths.
- Keep canonical skill packages, shared instructions, hook definitions,
  execution policies, and role charters under `../agent-assets/`.
- Keep provider capability/version mappings and renderers under
  `../adapters/runtimes/`.
- Keep reusable control-plane implementation artifacts under
  `platform/agent-control-plane/`.
- Keep explanatory notes, diagrams, and applied validation writeups in
  `docs/`.
- Keep domain-specific governance in the downstream domain repository
  that owns the domain surface.
- Avoid storing scratch diagrams, one-off exports, or retired template
  notes here after their durable content has been promoted.
