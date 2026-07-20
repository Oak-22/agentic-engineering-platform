# AI Knowledge Promotion Diagram Experiment

## Workflow

```text
Generate -> Import -> Human refine -> Inspect -> Preserve -> Regenerate
```

## Variables

Input mode:

- prose-only
- visual-diff-driven
- brief plus visual evidence
- Excalidraw-native

Source of truth:

- Mermaid source
- Excalidraw scene
- visual preservation brief

Model/provider:

- closed text/reasoning
- closed multimodal
- practical closed
- open/open-weight multimodal

## Fixed Inputs

- v1 Mermaid source
- v1 Mermaid-rendered diagram
- v1 human-refined Excalidraw export
- update brief when required by the path
- output format per path
- prompt wrapper per path
- evaluation rubric
- reviewer/process

Record the exact model, provider, surface, settings, and date for every
run.

## Measures

- semantic correctness
- manual visual preservation
- text wrapping
- arrow routing
- layout stability
- Mermaid diffability
- Excalidraw editability
- human cleanup
- repeatability
- next-generation usefulness

## Baseline

- Mermaid source: `00-baseline/v1-ai-knowledge-promotion.mmd`
- Excalidraw scene: `00-baseline/v1-ai-knowledge-promotion.excalidraw`
- Excalidraw export: `00-baseline/v1-ai-knowledge-promotion.png`
- update brief: `01-briefs/v2-ai-knowledge-promotion-update-brief.md`
- Mermaid render: `00-baseline/v1-ai-knowledge-promotion.mermaid-rendered.png`

The Mermaid render is generated from the raw source before Excalidraw
editing.

## Paths

### A1: Brief-Driven Mermaid Update

Inputs: v1 Mermaid source and update brief.

Output: revised Mermaid source.

Tests prose-driven source updates.

### A2a: Visual Diff Extraction

Inputs: Mermaid render and human-refined Excalidraw export.

Output: visual preservation brief.

Tests visual-diff extraction.

### A2b: Visual Preservation Mermaid Regeneration

Inputs: v1 Mermaid source and visual preservation brief.

Output: revised Mermaid source.

Tests conversion of visual observations into Mermaid constraints.

### A3: Brief + Visual Mermaid Update

Inputs: v1 Mermaid source, Mermaid render, human-refined Excalidraw
export, and update brief.

Output: revised Mermaid source.

Tests semantic and visual inputs together.

### B: Excalidraw-Native Update

Inputs: v1 Excalidraw scene, human-refined export, and update brief.

Output: revised Excalidraw scene and exported image. Mermaid output is
optional.

Tests scene-native editing.

## Provider Tracks

### Closed Text/Reasoning

Use for A1. Select the strongest available text/reasoning model.

### Closed Multimodal

Use as a control for A2a and A3 when available.

### Practical Closed

Use for cost/quality comparison.

### Open/Open-Weight Multimodal

Use for A2a, A2b, and A3 when the runtime and image inputs are
reproducible.

## Run Metadata

```yaml
run_id:
path:
provider:
model:
model_version_or_date:
surface:
host_or_runtime:
reasoning_or_effort_setting:
temperature:
vision_input_resolution:
date:
input_artifacts:
output_artifacts:
notes:
```

Leave non-applicable fields blank.

## Scoring

Score each output from 1 to 5 for every measure listed above.

## Next Steps

1. Generate the Mermaid baseline render.
2. Freeze the A1 prompt.
3. Select the A1 models.
4. Run A1.
5. Freeze the A2a prompt.
6. Select the A2/A3 models.
7. Run A2a, A2b, and A3.
8. Run B when scene-editing tooling is available.
9. Compare outputs and record reusable mechanics.
