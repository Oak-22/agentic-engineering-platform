# AI Knowledge Promotion Diagram Experiment

This folder contains the v1-to-v2 experiment for Mermaid-first and
Excalidraw-native diagram updates.

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

## Shared Artifacts

- `../baseline-v1/v1-ai-knowledge-promotion.mmd`
- `../baseline-v1/v1-ai-knowledge-promotion.excalidraw`
- `../baseline-v1/v1-ai-knowledge-promotion.png`
- `../briefs/v2-ai-knowledge-promotion-update-brief.md`
- `../briefs/architecture-diagram-update-brief-template.md`
