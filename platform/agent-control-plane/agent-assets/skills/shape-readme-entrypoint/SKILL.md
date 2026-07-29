---
name: shape-readme-entrypoint
description: Create, review, or simplify repository README files as lightweight, hands-on entry points while preserving deeper conceptual work in appropriate documentation. Use when writing or updating README.md, when a README is business-heavy or strategy-heavy, when quick-start value is buried, or when product positioning, architecture, decisions, and internal mental models need clearer artifact boundaries.
---

# Shape README Entrypoint

Make the README the shortest truthful path from discovery to demonstrated
value. Preserve useful conceptual material by routing it instead of
deleting it.

## Workflow

1. Inspect the README, manifest, runnable entry points, tests, and relevant
   docs. Identify the primary audience and shortest successful user journey.
2. Classify existing material:
   - `README.md`: identity, immediate value, install, run, example output,
     current capabilities, development commands, and deeper links.
   - `docs/product-thesis.md`: problem framing, positioning, business value,
     conceptual mental models, differentiation, and long-term direction.
   - `docs/architecture.md`: components, boundaries, data flow, contracts,
     and technical constraints.
   - decision or migration docs: historical choices, execution state, and
     change rationale.
3. Move misplaced material to the appropriate artifact. Preserve meaning,
   provenance, and useful nuance; do not merely discard verbose sections.
4. Shape the README in this default order:
   - project name and one-sentence description
   - quick start
   - small input/output or usage example
   - concise capability list
   - contributor setup and test command
   - links to deeper documentation
5. Put a working command within the first screen when the project is
   runnable. Prefer demonstrated behavior over aspirational claims.
6. Verify commands when practical. Do not document unavailable features or
   silently broaden product scope.

## Editing Rules

- Optimize the README for `discover -> understand -> run -> observe value`.
- Optimize the product thesis for `conceptualize -> position -> reason ->
  preserve direction`.
- Keep strategic positioning in the README to one or two short paragraphs.
- Link to deeper artifacts instead of duplicating them.
- Separate user instructions from contributor instructions.
- Preserve project-specific terminology when it improves comprehension.
- Avoid arbitrary compression for libraries that genuinely require API or
  compatibility documentation; keep the entry path clear and route detail
  behind links.

Use this routing question for each paragraph:

> Does a new reader need this before successfully using or evaluating the
> project?

Keep it in the README when the answer is yes. Route it when the answer is no.

## Product Thesis Shape

When conceptual material warrants `docs/product-thesis.md`, use only the
sections supported by the source material:

```markdown
# Product Thesis

## Thesis
## Problem
## Positioning
## System Value
## Boundaries
## Direction
```

Treat the product thesis as durable conceptual onboarding, not a second
README. Report which material moved and which commands were verified.
