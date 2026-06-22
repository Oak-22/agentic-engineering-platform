# Artifact Formatting Preferences

## Purpose

Use this instruction when writing or editing repository artifacts,
including code, documentation, diagrams, generated reports, manifests,
and agent-facing guidance.

The goal is not decorative consistency. The goal is to make artifacts
easier to read, review, and inherit across large repositories.


## Core Rule

Prefer formatting that reveals the artifact's conceptual structure.

When choosing between mechanically stable formatting and
meaning-carrying formatting, preserve meaning when human interpretation
is part of the artifact's purpose.

Examples:

```text
input before output
source before derived
before_value before after_value
expected before actual
identity before domain before keyword
validation before manifest
```


## Documentation Formatting

For substantial Markdown documents, use extra vertical spacing before
major sections to improve scanability in large repositories.

Rules:

- Use two blank lines before major `##` section headers.
- Keep one blank line between ordinary paragraphs, lists, code blocks,
  and nearby prose.
- In long narrative documents, use the existing repo's major-section
  rhythm when one exists. For example, some repositories use:

```md
<br>

---

<br>

## Next Major Section
```

- Do not force separators into short notes, small README files, or
  files whose existing local style is intentionally compact.
- Prefer section order that matches the workflow or concept order, not
  alphabetical order.


## Derive Local Style Before Writing

Before creating a new artifact in an existing repository, inspect nearby
examples that were already accepted into the repo.

Use those artifacts as evidence for:

- header depth and naming style
- spacing between major sections
- callout style
- list density
- code block use
- diagram labeling conventions
- ordering of fields, steps, and concepts

When a repository has a clearly evolved local style, follow it unless
the user explicitly asks for a new style.


## Code Formatting

Follow the language formatter and local style first.

When local style does not answer a formatting question:

- order code by dependency and reading flow
- keep helper functions near the logic they support when the module is
  small
- separate reusable capability from workflow sequencing
- avoid formatting churn unrelated to the requested change


## Generated Artifacts

Generated artifacts may be both machine-readable and explanatory.

For pure interchange files, stable sorted keys may be acceptable. For
human-reviewed manifests, reports, and evidence artifacts, preserve
semantic field order when it helps the reader understand the workflow.

Do not alphabetize fields when alphabetical order hides an important
sequence.


## Diagrams

For diagrams, preserve conceptual flow over visual novelty.

Prefer:

- left-to-right or top-to-bottom ordering that matches execution order
- clear boundaries between source, derived, validation, and manifest
  layers
- labels that match repository terminology
- grouping that reveals responsibility boundaries

Avoid diagram layouts that look balanced but imply the wrong order,
ownership, or dependency relationship.

