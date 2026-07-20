# v2 AI Knowledge Promotion Update Brief

## Source Artifacts

Semantic source:
- `docs/diagrams/ai-knowledge-promotion/experiment/00-baseline/v1-ai-knowledge-promotion.mmd`

Visual source:
- `docs/diagrams/ai-knowledge-promotion/experiment/00-baseline/v1-ai-knowledge-promotion.excalidraw`
- `docs/diagrams/ai-knowledge-promotion/experiment/00-baseline/v1-ai-knowledge-promotion.png`

Related context:
- `docs/periodic_learning_retrieval_system.md`
- `README.md`

## Task

Generate a revised Mermaid version of the diagram for v2.

Output target:
- `docs/diagrams/ai-knowledge-promotion/experiment/mode-a3-brief-visual/v2-ai-knowledge-promotion.mode-a3-brief-visual.mmd`

Do not edit the v1 files.

## Changes Needed

### Semantic Changes

- Remove excessive `<br>` usage. Line breaks should separate meaningful phrases, not individual words.
- Rename `4. Future Extension: Workflow-Derived Retrieval Layer` to remove “Future Extension.”
- Distinguish learning/retrieval prompts from generic reusable `.github/prompts/`.
- Replace `updates future prompts` with wording that makes clear these are learning prompts.
- Remove dotted “preserved from existing diagram” lines and labels.
- Clarify the `possible durable lesson` arrow so it flows back into the capture/promotion process, not ambiguous empty space.
- Reconsider whether `5. Interface to Feedforward / Feedback Lifecycle` should keep the numeric prefix, because the lifecycle is both downstream and upstream.

### Manual Visual Changes To Preserve

- Keep `load governance standards`, not `load governed standards`.
- Preserve user-adjusted spacing where visible in the Excalidraw/png version.
- Preserve improved arrow routing where semantically valid.
- Preserve the adjusted arrow-label placement around the `Durable Lesson` decision diamond.
- Do not reintroduce the old visual clutter from the original Mermaid.

### Concepts To Preserve

These concepts should remain integrated naturally, without “preserved” labels:

- Personal learning space
- Repo incident reports
- Domain case studies
- Global org standards
- Git repository / supporting infrastructure
- Confluence / SharePoint
- GitHub Wiki / Docs portal
- Architecture decisions
- Promotion path from repo to domain to global
- Proven reuse as a promotion signal
- Versioning, review, provenance, sync, and audit trail

## Output Requirements

- Produce raw Mermaid text only.
- Do not wrap the output in markdown fences if writing to `.mmd`.
- Optimize for Mermaid-to-Excalidraw import.
- Prefer stable node IDs so future diffs are meaningful.
- Preserve the existing architecture unless a requested change requires altering it.
