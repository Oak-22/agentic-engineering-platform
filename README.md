# Agentic Engineering Platform

The Agentic Engineering Platform is an internal developer platform for
governing, observing, and improving AI-assisted engineering workflows. It
brings together reusable agent-governance infrastructure, execution telemetry,
engineering tools, and evidence from real human-AI workflows. Product
repositories are downstream consumers rather than part of the platform itself.

## Platform Model

The repository is organized around a feedback loop:

```text
govern agent behavior
  -> execute engineering workflows
  -> capture telemetry and outcomes
  -> study human-AI collaboration
  -> promote validated lessons back into the platform
```

## Repository Structure

```text
agentic-engineering-platform/
├── platform/
│   ├── agent-control-plane/
│   ├── inference-telemetry-observatory/
│   ├── context-serialization-tooling/
│   └── developer-learning-retrieval/
├── evidence/
│   └── human-ai-collaboration-case-studies/
├── shared/
│   ├── schemas/
│   ├── contracts/
│   └── tooling/
├── docs/
│   ├── architecture/
│   ├── operations/
│   └── roadmap/
└── scripts/
```

### Platform domains

- [`platform/agent-control-plane/`](platform/agent-control-plane/) governs
  instruction discovery, runtime adapters, provenance, reusable skills, and
  auditable agent execution.
- [`platform/inference-telemetry-observatory/`](platform/inference-telemetry-observatory/)
  measures model usage, latency, token economics, routing decisions, and agent
  execution behavior.
- [`platform/context-serialization-tooling/`](platform/context-serialization-tooling/)
  provides independently packageable repository-orientation and context tools.
- [`platform/developer-learning-retrieval/`](platform/developer-learning-retrieval/)
  converts engineering activity into retrieval-practice and learning signals.

### Supporting boundaries

- [`evidence/`](evidence/) contains applied human-AI collaboration case studies
  used to validate and improve the platform.
- [`shared/`](shared/) owns cross-domain schemas, contracts, and reusable
  tooling that do not belong to a single platform component.
- [`docs/`](docs/) separates architecture, operations, and roadmap material.
- [`scripts/`](scripts/) is reserved for repository-wide automation.

## Intended Use

The platform supports teams and individual engineers building AI-native
development workflows. Its pieces can be evaluated together or adopted
independently:

- install governance patterns into another repository
- instrument an AI workflow with execution telemetry
- use reference tools to inspect and communicate repository structure
- study documented collaboration patterns before encoding new agent rules

Product repositories such as `myHealth` and
`digital-asset-processing-pipeline` remain separate consumers and proving
grounds rather than embedded platform components.

## Local Knowledge Overlay

Personal engineering notes may be mounted locally through the repository-root
`engineering-knowledge-base` symlink. This machine-specific overlay is
intentionally excluded from the canonical repository and does not define
product requirements or runtime contracts. The tracked public design surface
remains
[`docs/architecture/engineering-knowledge-base.md`](docs/architecture/engineering-knowledge-base.md).

## Development Workspace

Open this repository folder directly for platform-only development. For
bidirectional work with myHealth, use the machine-local cross-repository
workspace stored outside this repository under `~/Projects/dev/workspaces/`.

## Repository History

This monorepo preserves the commit histories of the original component
repositories. The parent repository is now the canonical integration point
for cross-component documentation, development, and future releases.

## License

Individual imported projects retain their existing license terms. A unified
platform-level license can be added when those terms have been reviewed.
