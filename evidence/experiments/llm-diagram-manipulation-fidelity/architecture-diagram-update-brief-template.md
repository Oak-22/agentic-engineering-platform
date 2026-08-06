# Architecture Diagram Update Brief Template

## Source Artifacts

Semantic source:
- `[path to current Mermaid source]`

Visual source:
- `[path to current Excalidraw source]`
- `[path to current exported diagram image]`

Related context:
- `[path to related architecture/design docs]`
- `[path to repo or project overview docs]`

## Task

Generate a revised Mermaid version of the diagram for `[version or iteration]`.

Output target:
- `[path to new Mermaid output]`

Do not edit:
- `[paths to source/baseline files that must remain unchanged]`

## Changes Needed

### Semantic Changes

- `[change in diagram meaning, naming, relationships, scope, or conceptual model]`
- `[change in arrows, labels, grouping, hierarchy, or artifact relationships]`
- `[change needed to align the diagram with current docs/code/repo reality]`

### Manual Visual Changes To Preserve

- `[manual Excalidraw layout, spacing, grouping, or arrow-routing change to preserve]`
- `[manual label placement, text wrapping, or visual hierarchy change to preserve]`
- `[visual clutter or old rendering behavior that should not be reintroduced]`

### Concepts To Preserve

These concepts should remain integrated naturally, without preservation metadata:

- `[concept/module/pathway to preserve]`
- `[concept/module/pathway to preserve]`
- `[concept/module/pathway to preserve]`

## Output Requirements

- Produce raw Mermaid text only.
- Do not wrap the output in markdown fences if writing to `.mmd`.
- Optimize for Mermaid-to-Excalidraw import.
- Prefer stable node IDs so future diffs are meaningful.
- Preserve the existing architecture unless a requested change requires altering it.
