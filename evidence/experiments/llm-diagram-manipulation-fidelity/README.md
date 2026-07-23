# LLM Diagram Manipulation Fidelity Experiment

This folder contains the v1-to-v2 experiment for comparing Mermaid-first and
Excalidraw-native LLM diagram updates. It is evidence about model and workflow
fidelity, rather than part of the agent control plane's runtime or canonical
documentation surface.

The subject under manipulation is the agent control plane's
[AI knowledge promotion diagram](../../../platform/agent-control-plane/docs/diagrams/ai-knowledge-promotion/README.md).
Its feedforward/feedback section is a boundary-level representation whose
[detailed lifecycle diagram](../../../platform/agent-control-plane/docs/diagrams/ai-knowledge-promotion/subcomponents/feedforward-feedback-change-lifecycle/feedforward-feedback-change-lifecycle.png)
expands the execution, review, correction, and promotion loop. Runs should
preserve that parent/detail relationship even when only the full diagram is
being edited.

The protocol is in [`experiment-design.md`](experiment-design.md).

## Matrix

| Path | Inputs | Output |
| --- | --- | --- |
| A1 | Mermaid source, update brief | Mermaid source |
| A2 | Mermaid source, Mermaid render, Excalidraw export | Mermaid source |
| A3 | A2 inputs, update brief | Mermaid source |
| B | Excalidraw scene, export, update brief | Excalidraw scene and image |

## Folders

- `00-baseline/`
- `01-briefs/`
- `mode-a1-brief/`
- `mode-a2-visual-diff/`
- `mode-a3-brief-visual/`
- `mode-b-excalidraw-native/`
- `comparison/`
- `model_card/`

## Shared Artifacts

- `00-baseline/v1-ai-knowledge-promotion.mmd`
- `00-baseline/v1-ai-knowledge-promotion.excalidraw`
- `00-baseline/v1-ai-knowledge-promotion.png`
- `01-briefs/v2-ai-knowledge-promotion-update-brief.md`

The reusable update-brief template is shared across diagram experiments:

- [`../architecture-diagram-update-brief-template.md`](../architecture-diagram-update-brief-template.md)
