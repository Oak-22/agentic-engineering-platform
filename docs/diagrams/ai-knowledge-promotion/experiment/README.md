# AI Knowledge Promotion Diagram Experiment

This folder tracks the `v1 -> v2` diagram-generation experiment for the
AI knowledge promotion / workflow-derived learning platform diagram.

The experiment compares Mermaid-first and Excalidraw-native update
paths so the diagram workflow can later be promoted into an
architecture-diagram-generation skill.

## Artifact Vocabulary

- Mermaid source: raw `.mmd` diagram code.
- Mermaid-rendered diagram: visual output rendered directly from
  Mermaid source before Excalidraw edits.
- Excalidraw scene: editable `.excalidraw` file.
- Excalidraw-exported image: `.png` or `.svg` exported from the
  Excalidraw scene after manual edits.
- Update brief: prose change request describing semantic edits,
  visual-preservation constraints, and output requirements.

## Experiment Matrix

| Path | Inputs | Purpose |
| --- | --- | --- |
| A1 | v1 Mermaid source + update brief | Test prose-driven Mermaid update. |
| A2 | v1 Mermaid source + v1 Mermaid-rendered diagram + v1 Excalidraw-exported image | Test visual-diff-driven preservation. |
| A3 | v1 Mermaid source + v1 Mermaid-rendered diagram + v1 Excalidraw-exported image + update brief | Test strongest Mermaid-first workflow. |
| B | v1 Excalidraw scene + update brief + MCP/tooling when available | Test Excalidraw-native update path. |

## Folders

- `00-baseline/`
  Defines the shared v1 artifacts and vocabulary.
- `01-briefs/`
  Stores concrete and generic invocation briefs.
- `mode-a1-brief/`
  Mermaid-first update using source plus prose brief.
- `mode-a2-visual-diff/`
  Mermaid-first update using source plus visual comparison evidence.
- `mode-a3-brief-visual/`
  Mermaid-first update using source, visual evidence, and prose brief.
- `mode-b-excalidraw-native/`
  Excalidraw-native path for MCP-assisted or direct scene editing.
- `comparison/`
  Cross-inspection notes, scoring, and observations.

## Shared Baseline Artifacts

The current baseline artifacts live in `baseline-v1/`:

- `../baseline-v1/v1-ai-knowledge-promotion.mmd`
- `../baseline-v1/v1-ai-knowledge-promotion.excalidraw`
- `../baseline-v1/v1-ai-knowledge-promotion.png`
- `../briefs/v2-ai-knowledge-promotion-update-brief.md`
- `../briefs/architecture-diagram-update-brief-template.md`

Future generated outputs should be stored in the mode-specific folders
unless there is a deliberate reason to promote one version back to the
top-level `docs/diagrams/` folder.
