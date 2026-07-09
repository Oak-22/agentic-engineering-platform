# Mode B: Excalidraw-Native Update

## Inputs

- v1 Excalidraw scene:
  `../../baseline-v1/v1-ai-knowledge-promotion.excalidraw`
- v1 Excalidraw-exported image:
  `../../baseline-v1/v1-ai-knowledge-promotion.png`
- Update brief:
  `../../briefs/v2-ai-knowledge-promotion-update-brief.md`

## Output Targets

- `v2-ai-knowledge-promotion.mode-b-excalidraw-native.excalidraw`
- Exported image:
  `v2-ai-knowledge-promotion.mode-b-excalidraw-native.png`
- Optional semantic source:
  `v2-ai-knowledge-promotion.mode-b-excalidraw-native.mmd`

## What This Tests

This path tests whether Excalidraw itself can become the editable source
of truth instead of using Mermaid as the only durable source.

It is intended for MCP-assisted or direct scene-level editing once an
Excalidraw MCP/tooling path is available in the working environment.

The main observation is whether scene-native editing better preserves:

- element positions
- arrows and bindings
- text wrapping
- grouping
- manual layout decisions
- export stability
