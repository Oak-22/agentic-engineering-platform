# Developer Learning Retrieval Service

Status: **Planned — design only**

This service will turn real AI-assisted engineering activity into short,
targeted retrieval-practice sessions. Its primary interaction is a daily
five-to-ten-minute developer quiz conducted through Codex or another
compatible agent surface.

## Intended Responsibilities

- consume learning signals from commits, debugging sessions, agent runs,
  and telemetry
- select concepts that merit reinforcement
- generate questions grounded in the developer's actual work
- schedule questions using spaced-repetition intervals
- require an unaided recall attempt before revealing explanations
- record confidence, misconceptions, and later retrieval outcomes
- promote durable insights into the engineering knowledge base

## Platform Relationships

```text
AI-assisted engineering activity
  -> telemetry observatory
  -> developer learning retrieval service
  -> 5–10 minute active-recall session
  -> engineering knowledge base
  -> instruction and workflow improvement
```

The service design is documented in [`design.md`](design.md).

Deferred feature concepts:

- [Shared Shell Assistance Gradient](features/shared-shell-assistance-gradient.md)
  explores three assistance interfaces over one continuous shell session as a
  source of learning and retention signals.

## Implemented Pieces

- The `show-me` skill
  (`platform/agent-control-plane/agent-assets/skills/show-me/`) is the
  first concrete slice: on deliberate request, it captures a
  diagram/explanation of a mechanism under discussion — resolved or still
  being worked through — into a single, machine-local, provider-neutral
  viewing cache, purely for reopening the rendered explanation later. It
  does not write into the real Engineering Knowledge Base (EKB) repo, or
  anywhere else — EKB is an optional, separate downstream overlay that
  could later consume this cache's output, not something `show-me` depends
  on or writes to directly. `design.md`'s mention of "an optional,
  machine-local `engineering-knowledge-base/`" (below) refers to EKB's own
  adoption symlink convention, unrelated to what `show-me` actually writes.
  `show-me` has no telemetry, scheduling, or quiz behavior; see
  Implementation Boundary.

## Implementation Boundary

No scheduler, quiz engine, Codex automation, or user interface has been
implemented yet, and no learning signals are consumed from commits,
debugging sessions, or telemetry. The `show-me` skill above is the one
implemented piece — a manually-invoked capture mechanism, not the
persistence layer or retrieval loop this directory otherwise still only
plans. This directory establishes the rest of the planned service boundary
without overstating its maturity.
