# Personal Learning Notes

This README defines the purpose of the personal learning notes section
of the engineering knowledge base.

Use this area to convert project execution into durable understanding
that is useful to both your future self and portfolio reviewers.

This section is the `personal` audience lane: capture quickly,
then selectively publish high-value lessons into shared knowledge.

## What This Should Demonstrate

In an enterprise context, learning notes should show:

- decision quality under real constraints
- clear understanding of systems, not isolated tools
- ability to identify and prevent recurring risks
- progression from task execution to engineering judgment

## Directory Intent

- `foundations/`: reusable technical foundations learned through work
- `case-studies/`: deep dives on specific incidents or design decisions

## How This Connects To Shared Knowledge

Personal notes are not required to be immediately repo/domain/global.
Treat them as draft learning artifacts.

When a note proves useful beyond personal reflection:

1. Publish as `shared` + `repo` guidance.
2. Promote to `shared` + `domain` when reused in related services.
3. Promote to `shared` + `global` when broadly stable.

Keep links between the personal draft and the shared canonical version.

## Enterprise-Oriented Note Types

Prefer notes that answer "how we apply this in production".

- architecture decision patterns
- debugging and observability playbooks
- reliability and incident-prevention lessons
- security and compliance constraints in implementation
- delivery workflows (CI/CD, rollout, rollback, change management)

## Naming Convention

Use descriptive, searchable filenames in kebab-case.

- `authz-patterns-in-internal-apis.md`
- `safe-schema-migration-checklist.md`
- `debugging-intermittent-ci-failures.md`
- `choosing-async-events-vs-sync-calls.md`

## Suggested Note Template

Use this structure for consistency:

1. Context: What project situation triggered this note?
2. Problem: What was hard or risky?
3. Applied Approach: What did you do and why?
4. Tradeoffs: What alternatives were considered?
5. Outcome: What changed (quality, reliability, speed, cost)?
6. Reuse Rule: When should this pattern be used again?
7. References: Links to PRs, incidents, runbooks, dashboards.

## Optional Personal Frontmatter

```yaml
---
audience: personal
scope: none                 # none | repo | domain | global
maturity: draft
promotion_candidate: false
related_shared: []
---
```
