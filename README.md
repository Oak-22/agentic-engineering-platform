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

- [`agent-instruction-control-plane/`](agent-instruction-control-plane/)
  A portable control plane for instruction discovery, runtime adapters,
  provenance, reusable skills, and auditable agent execution.

- [`ai-inference-telemetry-economics-observatory/`](ai-inference-telemetry-economics-observatory/)
  An observability service for measuring model usage, latency, token
  economics, routing decisions, and agent execution behavior.

- [`developer-learning-retrieval/`](developer-learning-retrieval/)
  A planned service that converts real engineering activity into daily
  five-to-ten-minute active-recall sessions for stronger retention.

- [`folder-structure-visualizer/`](folder-structure-visualizer/)
  An independently packageable developer-comprehension tool that maps
  filesystem and repository hierarchy for faster onboarding, clearer
  agent prompts, and shared human-agent structural context.

- [`ai-human-engineering-collaboration-case-studies/`](ai-human-engineering-collaboration-case-studies/)
  Applied case studies documenting human-AI collaboration patterns,
  failure modes, prompt refinement, and instruction-system evolution.

- [`docs/engineering-knowledge-base.md`](docs/engineering-knowledge-base.md)
  The planned public contract for capturing, promoting, retrieving, and
  governing engineering knowledge without publishing private notes.

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
remains [`docs/engineering-knowledge-base.md`](docs/engineering-knowledge-base.md).

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
