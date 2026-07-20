# Agentic Engineering Platform

The Agentic Engineering Platform is a unified framework for designing,
operating, observing, and improving AI-assisted engineering systems. It
brings together reusable agent-governance infrastructure, execution
telemetry, engineering tools, and evidence from real human-AI workflows.

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

### Components

- [`components/agent_instruction_control_plane/`](components/agent_instruction_control_plane/)
  A portable control plane for instruction discovery, runtime adapters,
  provenance, reusable skills, and auditable agent execution.

- [`components/engineering_knowledge_base/`](components/engineering_knowledge_base/)
  A planned portable contract for capturing, promoting, retrieving, and
  governing engineering knowledge without publishing private notes.

### Services

- [`services/ai_inference_telemetry_economics_observatory/`](services/ai_inference_telemetry_economics_observatory/)
  An observability service for measuring model usage, latency, token
  economics, routing decisions, and agent execution behavior.

- [`services/developer_learning_retrieval/`](services/developer_learning_retrieval/)
  A planned service that converts real engineering activity into daily
  five-to-ten-minute active-recall sessions for stronger retention.

### Tools

- [`tools/folder_structure_visualizer/`](tools/folder_structure_visualizer/)
  An independently packageable developer-comprehension tool that maps
  filesystem and repository hierarchy for faster onboarding, clearer
  agent prompts, and shared human-agent structural context.

### Research and Documentation

- [`docs/case_studies/`](docs/case_studies/)
  Applied case studies documenting human-AI collaboration patterns,
  failure modes, prompt refinement, and instruction-system evolution.

## Intended Use

The platform supports teams and individual engineers building AI-native
development workflows. Its pieces can be evaluated together or adopted
independently:

- install governance patterns into another repository
- instrument an AI workflow with execution telemetry
- use reference tools to inspect and communicate repository structure
- study documented collaboration patterns before encoding new agent rules

Product repositories such as `myHealth` and
`digital_asset_processing_pipeline` remain separate consumers and proving
grounds rather than embedded platform components.

## Local Knowledge Overlay

Personal engineering notes may be mounted locally as an
`engineering_knowledge_base` overlay inside a component or service. These
machine-specific overlays are intentionally excluded from the canonical
repository and do not define product requirements or runtime contracts.

## Development Workspace

Open [`Agentic_Engineering_Platform.code-workspace`](Agentic_Engineering_Platform.code-workspace)
in VS Code to work with the platform's component, service, and case-study
folders as a coordinated multi-root workspace.

## Repository History

This monorepo preserves the commit histories of the original component
repositories. The parent repository is now the canonical integration point
for cross-component documentation, development, and future releases.

## License

Individual imported projects retain their existing license terms. A unified
platform-level license can be added when those terms have been reviewed.
