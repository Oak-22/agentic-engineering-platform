---
description: "Portable general AI-agent collaboration rules."
applyTo: "**/*"
---
# General AI Agent Instructions

## Purpose

Use this instruction file as portable guidance for AI-assisted work
across repositories.

## Working Principles

- Inspect relevant files before proposing or making changes.
- Prefer local repository patterns over introducing new abstractions.
- Keep edits scoped to requested behavior.
- Preserve user-authored work and avoid reverting unrelated changes.
- Explain tradeoffs when decisions affect maintainability, contracts, or
  workflow semantics.
- Verify changes with the smallest useful command set.

## Safety And Privacy

- Do not expose secrets, credentials, tokens, private paths, or
  personal data in generated artifacts.
- Keep reusable guidance separate from repository-specific constraints.

## Review Stance

When asked for review, prioritize behavioral regressions, contract
mismatches, missing tests, stale docs, and boundary violations.
