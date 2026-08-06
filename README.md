# Agentic Engineering Platform

The Agentic Engineering Platform is an AI-native internal developer platform for
governing, observing, and improving AI-assisted engineering workflows. It
brings together reusable agent-governance infrastructure, execution telemetry,
engineering tools, and evidence from real human-AI workflows.

## Platform Model

The platform turns human intention into reusable agent behavior by encoding
procedures as skills, grounding them in governed supporting artifacts,
executing them within explicit task authority, and feeding observed outcomes
back into the system.


That loop maps onto three peer components: the Agent Control Plane governs
execution, Inference Telemetry observes behavior and outcomes, and Developer
Learning turns validated signals into reinforced understanding. Shared
Contracts & Schemas connect the three components, and telemetry and learning
feed improvements back into the Agent Control Plane.

<img alt="Agent Control Plane governs Shared Contracts and Schemas, which flow to Inference Telemetry and Developer Learning; both feed back to the Agent Control Plane, telemetry via a solid line and developer learning via a dotted line." src="agentic-control-plane-diagram.svg">

## Delivery Model

Use `workbench/local` as the private continuous capture-and-stewardship stream.
Shape coherent outcomes from that stream, then transfer selected commits,
files, or hunks in dependency order to Jira-keyed branches created from
current `main`. Reviewed pull requests advance `main`; the workbench does not.
See the [governed repository delivery guide](docs/operations/governed-repository-delivery.md).

## Repository Structure

```text
agentic-engineering-platform/
├── AGENTS.md
├── CLAUDE.md
├── .agents/
│   └── skills/
├── .codex/
│   ├── hooks/
│   └── hooks.json
├── .claude/
│   ├── hooks/
│   ├── rules/
│   └── skills/
├── .github/
│   ├── copilot-instructions.md
│   ├── instructions/
│   ├── agents/
│   ├── prompts/
│   ├── skills/
│   └── hooks/
├── platform/
│   ├── agent-control-plane/
│   │   ├── adapters/
│   │   │   ├── jira/
│   │   │   └── runtimes/
│   │   │       ├── claude/
│   │   │       ├── codex/
│   │   │       └── github-copilot/
│   │   ├── agent-assets/
│   │   │   ├── execution-policies/
│   │   │   ├── hooks/
│   │   │   ├── instructions/
│   │   │   ├── mcp-servers/
│   │   │   ├── role-charters/
│   │   │   └── skills/
│   │   ├── contracts/
│   │   └── scripts/
│   ├── inference-telemetry-observatory/
│   └── developer-learning-retrieval/
├── evidence/
│   └── human-ai-collaboration-case-studies/
├── shared/
│   ├── schemas/
│   ├── contracts/
│   └── tooling/
│       └── folder-structure-visualizer/
├── docs/
│   ├── architecture/
│   ├── operations/
│   └── roadmap/
└── scripts/
```

### Platform domains

- [`platform/agent-control-plane/`](platform/agent-control-plane/) governs
  instruction discovery, runtime adapters, provenance, reusable skills,
  governed action routing, and auditable agent execution.
- [`platform/inference-telemetry-observatory/`](platform/inference-telemetry-observatory/)
  measures model usage, latency, token economics, and agent execution
  behavior.
- [`platform/developer-learning-retrieval/`](platform/developer-learning-retrieval/)
  converts engineering activity into retrieval-practice and learning signals.

### Supporting boundaries

- [`AGENTS.md`](AGENTS.md), [`.agents/`](.agents/), [`.codex/`](.codex/),
  [`.claude/`](.claude/), and the agent-related paths under
  [`.github/`](.github/) are repository-root runtime-native installation
  surfaces. Their portable contracts, canonical assets, adapters, and design
  documentation remain owned by the Agent Control Plane component.
- [`evidence/`](evidence/) contains applied human-AI collaboration case studies
  used to validate and improve the platform.
- [`shared/`](shared/) owns cross-domain schemas, contracts, and reusable
  tooling that connect multiple pillars or do not belong to a single platform
  component. Potential reuse alone is not enough; at least two pillars must
  share the artifact's lifecycle or interface.
- [`docs/`](docs/) separates architecture, operations, and roadmap material.
- [`scripts/`](scripts/) is reserved for repository-wide integration and
  maintenance automation. Component-specific scripts remain with their owning
  platform pillar.

## Local Knowledge Overlay

Personal engineering notes may be mounted locally through the repository-root
`engineering-knowledge-base` symlink. This machine-specific overlay is
intentionally excluded from the canonical repository and does not define
product requirements or runtime contracts. The tracked public design surface
remains
[`docs/architecture/engineering-knowledge-base.md`](docs/architecture/engineering-knowledge-base.md).


## Repository History

This monorepo preserves the commit histories of the original component
repositories. The parent repository is now the canonical integration point
for cross-component documentation, development, and future releases.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
