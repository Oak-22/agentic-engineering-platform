---
description: "Formatting guidance for code-adjacent artifacts, docs, and agent-facing outputs."
applyTo: "**/*.{md,json,yml,yaml,toml,py,sh}"
---
# Artifact Formatting Preferences

## Core Rule

Prefer formatting that reveals conceptual structure.

When choosing between mechanically stable formatting and
meaning-carrying formatting, preserve meaning when human interpretation
is part of the artifact's purpose.

## Documentation

- Use clear heading hierarchy and scannable section order.
- Preserve existing local style where one exists.
- Avoid decorative churn unrelated to requested changes.

## Generated Artifacts

For human-reviewed manifests or reports, preserve semantic field order
when ordering communicates workflow meaning.
