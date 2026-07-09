# Documentation Map

This folder holds explanatory material for the AI Agent Instruction
Control Plane. It is not the minimum install surface. The minimum
control-plane template lives under `.github/` and
`engineering_knowledge_base/`.

## Start Here

- [Applied Validation Through myHealth](applied-validation-through-myhealth.md)
  Explains how `myHealth` acts as the applied validation target for the
  control-plane pattern.
- [Feedforward Feedback Change Lifecycle](diagrams/feedforward-feedback-change-lifecycle/feedforward-feedback-change-lifecycle.png)
  Visualizes how feedforward instructions, feedback checks, human
  review, and promotion loops interact.
- [Workflow-Derived Retrieval](periodic_learning_retrieval_system.md)
  Describes a future extension for turning engineering activity into
  learning and retrieval signals.

## Diagrams

- [feedforward-feedback-change-lifecycle.excalidraw](diagrams/feedforward-feedback-change-lifecycle/feedforward-feedback-change-lifecycle.excalidraw)
  Source file for the lifecycle diagram.
- [feedforward-feedback-change-lifecycle.png](diagrams/feedforward-feedback-change-lifecycle/feedforward-feedback-change-lifecycle.png)
  Exported image for docs, portfolio use, and review.
- [AI Knowledge Promotion Diagram](diagrams/ai-knowledge-promotion/README.md)
  Diagram family for personal/team/org knowledge capture, promotion,
  retrieval, and integration.
- [AI Knowledge Promotion Diagram Experiment](diagrams/ai-knowledge-promotion/experiment/README.md)
  Scaffold for comparing Mermaid-first and Excalidraw-native diagram
  update workflows.

## Strategy

- [Strategy Notes](strategy/README.md)
  Index for domain-agnostic strategy notes.
- [Invisible Systems Thesis](strategy/invisible-systems-thesis.md)
  The broad thesis behind making authority, evidence, provenance,
  uncertainty, review, and consequences explicit enough to govern.

## Placement Rules

- Keep reusable control-plane implementation artifacts in `.github/`.
- Keep explanatory notes, diagrams, and applied validation writeups in
  `docs/`.
- Keep domain-specific governance in the downstream domain repository
  that owns the domain surface.
- Avoid storing scratch diagrams, one-off exports, or retired template
  notes here after their durable content has been promoted.
