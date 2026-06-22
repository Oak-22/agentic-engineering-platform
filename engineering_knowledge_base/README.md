# Engineering Knowledge Base

This README defines the purpose of the repository's engineering
knowledge base.

This directory captures workflow-derived learning artifacts that should
outlive a single task or AI chat session.

## Purpose

AI can accelerate delivery while also externalizing reasoning.
This structure helps preserve what the team learned while doing the
work.

In practice, this repository should prioritize repo-level context while
remaining compatible with broader organizational knowledge sharing.

## Sections

- `incident_reports/`
- `personal_learning_notes/`

## Knowledge Model

Use two independent dimensions for every entry:

- `audience`: `personal` or `shared`
- `scope`: `repo`, `domain`, `global` (primarily for `shared` entries)

Rules:

1. `personal` notes are fast-capture learning artifacts for individual
    developers.
2. `shared` notes are curated and intended for team reuse.
3. Default publication target is `shared` + `repo`.
4. Promote to `domain` or `global` only after reuse evidence.

This approach supports both:

- `personal -> shared` knowledge maturation
- `repo -> domain -> global` scope promotion

## Curation Standard

Keep entries concise and evidence-based.

- Prefer concrete examples from real tasks over generic definitions.
- Include impact signals when possible (latency, defect reduction,
  stability improvements, development speed).
- Capture what changed in your decision process after each lesson.

## Suggested Metadata

Use lightweight frontmatter for traceability:

```yaml
---
audience: shared            # personal | shared
scope: repo                 # repo | domain | global | none
maturity: validated         # draft | validated | canonical
promotion_candidate: false
validated_in_repos: []
related_global: []
related_local: []
---
```

## Fragmentation Guardrails

Partitioning is useful until it increases retrieval cost.

Use these checks:

1. If guidance drifts across multiple copies, define one authority.
2. If engineers cannot find the source in under 30 seconds,
   simplify structure.
3. If updates require edits in many files, consolidate and link.
4. If a repo note is reused in multiple repositories, promote it.
