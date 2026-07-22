# Platform Domains

This directory contains the runtime and developer-facing systems that make up
the Agentic Engineering Platform.

- [`agent-control-plane/`](agent-control-plane/) governs instruction discovery,
  runtime adapters, provenance, and auditable execution.
- [`inference-telemetry-observatory/`](inference-telemetry-observatory/) measures
  model usage, latency, token economics, routing, and execution behavior.
- [`context-serialization-tooling/`](context-serialization-tooling/) provides
  independently packageable repository-orientation and context tools.
- [`developer-learning-retrieval/`](developer-learning-retrieval/) turns
  engineering activity into retrieval-practice and learning signals.

Components should remain independently testable and packageable. Cross-domain
interfaces belong under [`../shared/`](../shared/).
