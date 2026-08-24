# Evidence

This directory contains applied observations and case studies from real
human-AI engineering workflows. Evidence informs platform changes but is not a
runtime dependency of the platform components.

- [`human-ai-collaboration-case-studies/`](human-ai-collaboration-case-studies/)
  documents collaboration patterns, failure modes, prompt refinement, and
  instruction-system evolution.
- [`experiments/llm-diagram-manipulation-fidelity/`](experiments/llm-diagram-manipulation-fidelity/)
  compares how LLM workflows preserve semantics, layout, routing, and native
  editability while revising architecture diagrams.
- [`experiments/repo-context-handoff-across-models/`](experiments/repo-context-handoff-across-models/)
  measures whether a quarantined, session-derived context handoff improves a
  new agent session's repository understanding.
- [`side-effects/`](side-effects/) records behavior a component produced
  outside its declared contract, what came to depend on it, and whether the
  resolution was to declare the behavior or remove the dependency.
