# Mode A2: Visual-Diff-Driven Mermaid Update

## Inputs

- v1 Mermaid source:
  `../../baseline-v1/v1-ai-knowledge-promotion.mmd`
- v1 Mermaid-rendered diagram:
  `../00-baseline/v1-ai-knowledge-promotion.mermaid-rendered.png`
- v1 Excalidraw-exported image:
  `../../baseline-v1/v1-ai-knowledge-promotion.png`

## Output Targets

- `v2-ai-knowledge-promotion.mode-a2-visual-diff.mmd`
- Optional rendered output:
  `v2-ai-knowledge-promotion.mode-a2-visual-diff.png`
- Optional Excalidraw import:
  `v2-ai-knowledge-promotion.mode-a2-visual-diff.excalidraw`

## What This Tests

This path tests whether the skill can infer human visual intent by
comparing the raw Mermaid-rendered diagram against the manually refined
Excalidraw export.

It should preserve visible manual changes where possible without
depending on a detailed prose brief.
