# Platform Domains

This directory contains the runtime and developer-facing systems that make up
the Agentic Engineering Platform.

- [`agent-control-plane/`](agent-control-plane/) governs instruction discovery,
  runtime adapters, provenance, governed actions, and auditable execution.
- [`inference-telemetry-observatory/`](inference-telemetry-observatory/) measures
  model usage, latency, token economics, and execution behavior.
- [`developer-learning-retrieval/`](developer-learning-retrieval/) turns
  engineering activity into retrieval-practice and learning signals.

These three pillars remain independently testable and packageable. Shared data
schemas, interface contracts, and cross-cutting tools belong under
[`../shared/`](../shared/) only when multiple pillars concretely share their
lifecycle or interface. Repository-wide integration commands remain under
[`../scripts/`](../scripts/); component implementation scripts remain with
their owning pillar.
